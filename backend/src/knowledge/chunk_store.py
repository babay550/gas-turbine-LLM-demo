"""ChunkStore — 混合检索引擎：BM25 关键词 + ZhiPu Embedding 语义向量 + RRF 融合。

架构：
  1. Heading 级分块 — 按 ## 二级标题拆分词条，保留元数据
  2. BM25 索引 — rank-bm25 + 中文 bigram 分词
  3. ZhiPu Embedding-3 — 在线 API 向量编码（可替换为本地模型）
  4. RRF 融合 — 倒数排名融合，k=60
  5. 增量更新 — SHA-256 文件哈希检测变更
"""

import hashlib
import json
import logging
import os
import pickle
import re
from typing import Optional

import numpy as np

from src.config import get_settings

logger = logging.getLogger(__name__)


# ─── 中文分词 ───

def chinese_tokenize(text: str) -> list[str]:
    """中文分词：按标点拆分词组 + 字符级 bigram。"""
    text_lower = text.lower()
    raw_terms = [t for t in re.split(r"[\s，。、？！；：""''（）【】《》\n\r]+", text_lower) if t]
    terms = []
    for t in raw_terms:
        if len(t) <= 2:
            terms.append(t)
        else:
            terms.append(t)
            for i in range(len(t) - 1):
                terms.append(t[i:i + 2])
    return terms


# ─── Heading 级分块 ───

def chunk_by_heading(content: str, max_size: int = 800) -> list[dict]:
    """按 ## 二级标题拆分词条内容为 chunks。"""
    sections = re.split(r"\n(?=#{2,3}\s)", content)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        heading_match = re.match(r"^#{2,3}\s+(.+)", section)
        heading = heading_match.group(1).strip() if heading_match else ""
        body = re.sub(r"^#{2,3}\s+.+\n?", "", section).strip() if heading_match else section
        if not body:
            continue
        if len(body) <= max_size:
            chunks.append({"heading": heading, "content": body})
        else:
            for sub in _split_by_paragraph(body, max_size):
                chunks.append({"heading": heading, "content": sub})
    return chunks


def _split_by_paragraph(text: str, max_size: int) -> list[str]:
    """按段落边界切分超长文本。"""
    paragraphs = re.split(r"\n\n+", text)
    parts = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 2 > max_size and current:
            parts.append(current.strip())
            current = p
        else:
            current = current + "\n\n" + p if current else p
    if current.strip():
        parts.append(current.strip())
    return parts


# ─── ZhiPu Embedding API ───

class EmbeddingProvider:
    """向量编码 — 默认使用 ZhiPu embedding-3 在线 API。

    # LOCAL: 本地化替代方案
    # 将 _encode_batch 方法替换为本地模型推理：
    #
    # from sentence_transformers import SentenceTransformer
    # self.model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
    # embeddings = self.model.encode(texts, normalize_embeddings=True)
    # return embeddings.astype(np.float32)
    """

    def __init__(self):
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            settings = get_settings()
            self._available = bool(settings.zhipu_api_key)
        return self._available

    def encode(self, texts: list[str]) -> Optional[np.ndarray]:
        """批量编码文本为向量。返回 (N, dim) 的 numpy 数组，失败返回 None。"""
        if not self.available or not texts:
            return None
        settings = get_settings()
        batch_size = settings.embedding_batch_size
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            emb = self._encode_batch(batch, settings)
            if emb is None:
                return None
            all_embeddings.append(emb)
        return np.vstack(all_embeddings)

    def _encode_batch(self, texts: list[str], settings) -> Optional[np.ndarray]:
        """调用 ZhiPu embedding API 编码一个批次。"""
        import httpx
        try:
            resp = httpx.post(
                "https://open.bigmodel.cn/api/paas/v4/embeddings",
                headers={"Authorization": f"Bearer {settings.zhipu_api_key}"},
                json={
                    "model": settings.zhipu_embedding_model,
                    "input": texts,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
            return np.array(embeddings, dtype=np.float32)
        except Exception as e:
            logger.warning("ZhiPu embedding API 调用失败: %s", e)
            return None


# ─── ChunkStore 主类 ───

class ChunkStore:
    """混合检索引擎：BM25 + Embedding + RRF。"""

    def __init__(self, wiki_manager):
        self.wiki_manager = wiki_manager
        self.settings = get_settings()

        # 存储目录
        self.store_dir = os.path.join(
            os.path.dirname(wiki_manager.root), "data", "chunk_store"
        )
        os.makedirs(self.store_dir, exist_ok=True)

        # 索引数据
        self.chunks: list[dict] = []
        self.file_hashes: dict[str, str] = {}
        self._bm25 = None
        self._vectors: Optional[np.ndarray] = None
        self._embedding = EmbeddingProvider()

        # 启动时加载已有索引
        self._load()

    # ─── 增量重建 ───

    def rebuild_index(self):
        """增量重建索引：仅处理变更的词条文件。"""
        all_entries = self.wiki_manager._scan_all_files()
        current_hashes = {}
        changed_files = set()

        for entry in all_entries:
            if not entry.file_path:
                continue
            file_hash = _file_hash(entry.file_path)
            current_hashes[entry.id] = file_hash
            if self.file_hashes.get(entry.id) != file_hash:
                changed_files.add(entry.id)

        # 删除已不存在的词条
        removed_ids = set(self.file_hashes.keys()) - {e.id for e in all_entries}
        if removed_ids:
            self.chunks = [c for c in self.chunks if c["entry_id"] not in removed_ids]

        if not changed_files and not removed_ids:
            logger.info("ChunkStore: 索引无变更，跳过重建")
            return

        logger.info("ChunkStore: 检测到 %d 个变更文件, %d 个删除", len(changed_files), len(removed_ids))

        # 移除变更词条的旧 chunks
        self.chunks = [c for c in self.chunks if c["entry_id"] not in changed_files]

        # 重新分块变更词条
        entry_map = {e.id: e for e in all_entries}
        new_chunks = []
        for eid in changed_files:
            entry = entry_map.get(eid)
            if not entry:
                continue
            entry_chunks = self._chunk_entry(entry)
            new_chunks.extend(entry_chunks)

        self.chunks.extend(new_chunks)
        self.file_hashes = current_hashes

        # 重建 BM25 索引
        self._build_bm25()

        # 重建向量（仅当 embedding 可用）
        if self._embedding.available:
            self._build_vectors()

        self._save()
        logger.info("ChunkStore: 索引重建完成，共 %d 个 chunks", len(self.chunks))

    def _chunk_entry(self, entry) -> list[dict]:
        """将单个词条拆分为 chunks。"""
        raw_chunks = chunk_by_heading(entry.content, self.settings.chunk_max_size)
        if not raw_chunks:
            raw_chunks = [{"heading": "", "content": entry.content[:self.settings.chunk_max_size]}]

        result = []
        for idx, rc in enumerate(raw_chunks):
            result.append({
                "entry_id": entry.id,
                "title": entry.title,
                "type": entry.type,
                "category": entry.category,
                "heading": rc["heading"],
                "content": rc["content"],
                "chunk_index": idx,
                "tags": entry.tags,
            })
        return result

    # ─── BM25 ───

    def _build_bm25(self):
        """构建 BM25 索引。"""
        from rank_bm25 import BM25Okapi
        if not self.chunks:
            self._bm25 = None
            return
        tokenized = [chinese_tokenize(c["content"]) for c in self.chunks]
        self._bm25 = BM25Okapi(tokenized)

    def _bm25_search(self, query: str, limit: int) -> list[tuple[int, float]]:
        """BM25 检索，返回 [(chunk_index, score), ...]。"""
        if not self._bm25 or not self.chunks:
            return []
        tokens = chinese_tokenize(query)
        scores = self._bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:limit]
        return [(int(i), float(scores[i])) for i in top_indices if scores[i] > 0]

    # ─── Embedding 向量 ───

    def _build_vectors(self):
        """构建所有 chunks 的向量。"""
        texts = [c["content"] for c in self.chunks]
        if not texts:
            self._vectors = None
            return
        self._vectors = self._embedding.encode(texts)
        if self._vectors is not None:
            # L2 归一化，后续 cosine = dot product
            norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1
            self._vectors = self._vectors / norms

    def _embedding_search(self, query: str, limit: int) -> list[tuple[int, float]]:
        """向量检索，返回 [(chunk_index, score), ...]。"""
        if self._vectors is None or not self.chunks:
            return []
        query_vec = self._embedding.encode([query])
        if query_vec is None:
            return []
        # 归一化查询向量
        query_vec = query_vec[0]
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm
        # cosine similarity = dot product（已归一化）
        scores = self._vectors @ query_vec
        top_indices = np.argsort(scores)[::-1][:limit]
        return [(int(i), float(scores[i])) for i in top_indices if scores[i] > 0.1]

    # ─── RRF 融合 ───

    def _rrf_fuse(
        self,
        bm25_results: list[tuple[int, float]],
        emb_results: list[tuple[int, float]],
        limit: int,
    ) -> list[int]:
        """RRF 融合排序，返回 top-N chunk 索引。"""
        k = self.settings.rrf_k
        scores: dict[int, float] = {}

        for rank, (idx, _) in enumerate(bm25_results, 1):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank)

        for rank, (idx, _) in enumerate(emb_results, 1):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank)

        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in sorted_items[:limit]]

    # ─── 混合检索入口 ───

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """混合检索：BM25 + Embedding + RRF 融合。"""
        if not self.chunks:
            return []

        bm25_results = self._bm25_search(query, limit * 3)

        if self._vectors is not None and self._embedding.available:
            emb_results = self._embedding_search(query, limit * 3)
            fused_indices = self._rrf_fuse(bm25_results, emb_results, limit)
            # 构建 rank 信息
            bm25_rank_map = {idx: rank for rank, (idx, _) in enumerate(bm25_results, 1)}
            emb_rank_map = {idx: rank for rank, (idx, _) in enumerate(emb_results, 1)}
        else:
            # BM25-only fallback
            fused_indices = [idx for idx, _ in bm25_results[:limit]]
            bm25_rank_map = {idx: rank for rank, (idx, _) in enumerate(bm25_results, 1)}
            emb_rank_map = {}

        results = []
        for idx in fused_indices:
            chunk = self.chunks[idx]
            rrf_score = 0.0
            bm25_rank = bm25_rank_map.get(idx)
            emb_rank = emb_rank_map.get(idx)
            k = self.settings.rrf_k
            if bm25_rank:
                rrf_score += 1.0 / (k + bm25_rank)
            if emb_rank:
                rrf_score += 1.0 / (k + emb_rank)

            results.append({
                "entry_id": chunk["entry_id"],
                "title": chunk["title"],
                "type": chunk["type"],
                "category": chunk["category"],
                "heading": chunk["heading"],
                "content": chunk["content"],
                "score": round(rrf_score, 6),
                "bm25_rank": bm25_rank,
                "embedding_rank": emb_rank,
                "tags": chunk.get("tags", []),
            })

        return results

    # ─── 持久化 ───

    def _save(self):
        """保存索引到磁盘。"""
        # chunks
        chunks_path = os.path.join(self.store_dir, "chunks.json")
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)

        # file hashes
        hashes_path = os.path.join(self.store_dir, "file_hashes.json")
        with open(hashes_path, "w", encoding="utf-8") as f:
            json.dump(self.file_hashes, f, ensure_ascii=False, indent=2)

        # BM25
        if self._bm25 is not None:
            bm25_path = os.path.join(self.store_dir, "bm25_state.pkl")
            with open(bm25_path, "wb") as f:
                pickle.dump(self._bm25, f)

        # vectors
        if self._vectors is not None:
            vec_path = os.path.join(self.store_dir, "vectors.npy")
            np.save(vec_path, self._vectors)

    def _load(self):
        """从磁盘加载已有索引。"""
        chunks_path = os.path.join(self.store_dir, "chunks.json")
        if os.path.exists(chunks_path):
            with open(chunks_path, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            logger.info("ChunkStore: 加载 %d 个 chunks", len(self.chunks))

        hashes_path = os.path.join(self.store_dir, "file_hashes.json")
        if os.path.exists(hashes_path):
            with open(hashes_path, "r", encoding="utf-8") as f:
                self.file_hashes = json.load(f)

        bm25_path = os.path.join(self.store_dir, "bm25_state.pkl")
        if os.path.exists(bm25_path):
            with open(bm25_path, "rb") as f:
                self._bm25 = pickle.load(f)

        vec_path = os.path.join(self.store_dir, "vectors.npy")
        if os.path.exists(vec_path):
            self._vectors = np.load(vec_path)
            logger.info("ChunkStore: 加载向量 %s", self._vectors.shape)


def _file_hash(path: str) -> str:
    """计算文件 SHA-256 哈希。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()[:16]
