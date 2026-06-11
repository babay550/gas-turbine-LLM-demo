"""Wiki 文件管理器 — 对 knowledge/wiki/ 目录的 CRUD、搜索、索引维护。"""

import logging
import os
import re
from datetime import datetime
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

WIKI_SUBDIRS = ["content", "entity", "concept", "comparative", "overview"]


class WikiEntry:
    """单条 wiki 词条。"""

    __slots__ = ("frontmatter", "content", "file_path")

    def __init__(self, frontmatter: dict, content: str, file_path: str = ""):
        self.frontmatter = frontmatter
        self.content = content
        self.file_path = file_path

    @property
    def id(self) -> str:
        return self.frontmatter.get("id", "")

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", "")

    @property
    def type(self) -> str:
        return self.frontmatter.get("type", "content_summary")

    @property
    def category(self) -> str:
        return self.frontmatter.get("category", "")

    @property
    def tags(self) -> list[str]:
        return self.frontmatter.get("tags", [])

    def to_meta_dict(self) -> dict:
        """返回用于列表展示的元数据字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "category": self.category,
            "tags": self.tags,
            "equipment": self.frontmatter.get("equipment", ""),
            "severity": self.frontmatter.get("severity", ""),
            "source_file": self.frontmatter.get("source_file", ""),
            "concept_subcategory": self.frontmatter.get("concept_subcategory", ""),
            "related_entries": self.frontmatter.get("related_entries", []),
            "created": self.frontmatter.get("created", ""),
            "updated": self.frontmatter.get("updated", ""),
        }


class WikiManager:
    """管理 knowledge/ 目录下的所有 wiki 文件操作。"""

    def __init__(self, knowledge_root: str):
        self.root = os.path.abspath(knowledge_root)
        self.wiki_dir = os.path.join(self.root, "wiki")
        self.raw_dir = os.path.join(self.root, "raw")
        self._chunk_store = None
        self._ensure_dirs()

    @property
    def chunk_store(self):
        """懒加载 ChunkStore。"""
        if self._chunk_store is None:
            try:
                from src.knowledge.chunk_store import ChunkStore
                self._chunk_store = ChunkStore(self)
            except Exception as e:
                logger.warning("ChunkStore 加载失败，将使用 bigram 搜索: %s", e)
        return self._chunk_store

    # ------------------------------------------------------------------
    # 目录初始化
    # ------------------------------------------------------------------

    def _ensure_dirs(self):
        for d in [self.root, self.raw_dir, os.path.join(self.raw_dir, "assets")]:
            os.makedirs(d, exist_ok=True)
        for sub in WIKI_SUBDIRS:
            os.makedirs(os.path.join(self.wiki_dir, sub), exist_ok=True)
        for fname in ["index.md", "log.md"]:
            fpath = os.path.join(self.wiki_dir, fname)
            if not os.path.exists(fpath):
                with open(fpath, "w", encoding="utf-8") as f:
                    title = "内容索引" if fname == "index.md" else "操作日志"
                    f.write(f"# {title}\n\n")

    # ------------------------------------------------------------------
    # Frontmatter 解析 / 序列化
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """从 markdown 文本中解析 YAML frontmatter，返回 (frontmatter, body)。"""
        if not text.startswith("---"):
            return {}, text
        end = text.find("\n---", 3)
        if end == -1:
            return {}, text
        fm_text = text[3:end].strip()
        body = text[end + 4:].strip()
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
        return fm, body

    @staticmethod
    def _serialize_entry(frontmatter: dict, content: str) -> str:
        """将 frontmatter + content 序列化为完整 markdown 文本。"""
        fm = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"---\n{fm}---\n\n{content}\n"

    # ------------------------------------------------------------------
    # ID 生成
    # ------------------------------------------------------------------

    def _next_id(self) -> str:
        """生成下一个 W### 格式的 ID。"""
        max_num = 0
        for entry in self._scan_all_files():
            eid = entry.frontmatter.get("id", "")
            m = re.match(r"W(\d+)", eid)
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"W{max_num + 1:03d}"

    # ------------------------------------------------------------------
    # 文件扫描
    # ------------------------------------------------------------------

    def _scan_all_files(self) -> list[WikiEntry]:
        """扫描 wiki/ 下所有 .md 文件（排除 index.md 和 log.md）。"""
        entries = []
        for sub in WIKI_SUBDIRS:
            sub_dir = os.path.join(self.wiki_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            for fname in os.listdir(sub_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(sub_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    fm, body = self._parse_frontmatter(text)
                    if fm:
                        entries.append(WikiEntry(fm, body, fpath))
                except Exception as e:
                    logger.warning("读取 wiki 文件失败 %s: %s", fpath, e)
        return entries

    def _entry_dir(self, entry_type: str) -> str:
        """根据词条类型返回对应的子目录。"""
        type_to_dir = {
            "content_summary": "content",
            "entity": "entity",
            "concept": "concept",
            "comparative": "comparative",
            "overview": "overview",
        }
        return os.path.join(self.wiki_dir, type_to_dir.get(entry_type, "content"))

    def _find_entry_file(self, entry_id: str) -> Optional[str]:
        """根据 ID 查找词条文件路径。"""
        for sub in WIKI_SUBDIRS:
            sub_dir = os.path.join(self.wiki_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            for fname in os.listdir(sub_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(sub_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    fm, _ = self._parse_frontmatter(text)
                    if fm.get("id") == entry_id:
                        return fpath
                except Exception:
                    continue
        return None

    # ------------------------------------------------------------------
    # CRUD 操作
    # ------------------------------------------------------------------

    def create_entry(self, frontmatter: dict, content: str) -> WikiEntry:
        """创建新 wiki 词条，自动生成 ID 并写入文件。"""
        entry_id = self._next_id()
        now = datetime.now().strftime("%Y-%m-%d")
        frontmatter.setdefault("id", entry_id)
        frontmatter.setdefault("created", now)
        frontmatter.setdefault("updated", now)

        entry_type = frontmatter.get("type", "content_summary")
        target_dir = self._entry_dir(entry_type)

        # 文件名：ID + 标题简写
        safe_title = re.sub(r'[\\/:*?"<>|]', "", frontmatter.get("title", "untitled"))[:30]
        filename = f"{entry_id}_{safe_title}.md"
        fpath = os.path.join(target_dir, filename)

        text = self._serialize_entry(frontmatter, content)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(text)

        entry = WikiEntry(frontmatter, content, fpath)
        self.rebuild_index()
        return entry

    def get_entry(self, entry_id: str) -> Optional[WikiEntry]:
        """获取单条 wiki 词条。"""
        fpath = self._find_entry_file(entry_id)
        if not fpath:
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        fm, body = self._parse_frontmatter(text)
        return WikiEntry(fm, body, fpath) if fm else None

    def update_entry(self, entry_id: str, frontmatter_updates: dict, content: Optional[str] = None) -> Optional[WikiEntry]:
        """更新 wiki 词条的 frontmatter 和/或正文。"""
        fpath = self._find_entry_file(entry_id)
        if not fpath:
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        fm, body = self._parse_frontmatter(text)
        fm.update(frontmatter_updates)
        fm["updated"] = datetime.now().strftime("%Y-%m-%d")
        new_content = content if content is not None else body

        new_text = self._serialize_entry(fm, new_content)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_text)

        # 如果类型变了可能需要移动文件
        old_type = text  # 旧文本中提取
        new_type = fm.get("type", "content_summary")
        new_dir = self._entry_dir(new_type)
        if os.path.dirname(fpath) != new_dir:
            new_fpath = os.path.join(new_dir, os.path.basename(fpath))
            os.rename(fpath, new_fpath)
            fpath = new_fpath

        self.rebuild_index()
        return WikiEntry(fm, new_content, fpath)

    def delete_entry(self, entry_id: str) -> bool:
        """删除 wiki 词条。"""
        fpath = self._find_entry_file(entry_id)
        if not fpath:
            return False
        os.remove(fpath)
        self.rebuild_index()
        return True

    # ------------------------------------------------------------------
    # 列表 / 搜索
    # ------------------------------------------------------------------

    def list_entries(
        self,
        entry_type: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """列出 wiki 词条，支持筛选和分页。返回 (entries_meta_list, total)。"""
        all_entries = self._scan_all_files()

        filtered = []
        query_lower = search.lower() if search else ""
        for entry in all_entries:
            if entry_type and entry.type != entry_type:
                continue
            if category and entry.category != category:
                continue
            if tag and tag not in entry.tags:
                continue
            if query_lower:
                # Safely build searchable text, guarding against None values in frontmatter/tags
                title_s = entry.title or ""
                category_s = entry.category or ""
                tags_s = " ".join([t for t in (entry.tags or []) if t])
                content_s = (entry.content or "").lower()
                equipment_s = str(entry.frontmatter.get("equipment") or "")
                searchable = " ".join([title_s, category_s, tags_s, content_s, equipment_s]).lower()
                if query_lower not in searchable:
                    continue
            filtered.append(entry.to_meta_dict())

        total = len(filtered)
        start = (page - 1) * page_size
        page_items = filtered[start:start + page_size]
        return page_items, total

    def search_entries(self, query: str, limit: int = 20, use_hybrid: bool = True) -> list[dict]:
        """全文搜索 — 优先使用混合检索（BM25+Embedding+RRF），回退到 bigram 匹配。"""
        if use_hybrid:
            cs = self.chunk_store
            if cs and getattr(cs, 'chunks', None):
                try:
                    results = cs.search(query, limit=limit)
                    if results:
                        return results
                except Exception as e:
                    logger.exception("ChunkStore search failed, falling back to bigram: %s", e)

        # Fallback: 原有 bigram 搜索
        all_entries = self._scan_all_files()
        query_lower = query.lower()

        # 1. 按空格/标点拆分为词组
        import re as _re
        raw_terms = [t for t in _re.split(r"[\s，。、？！；：""''（）【】《》]+", query_lower) if t]

        # 2. 对长度 > 4 的词组（中文无分隔），提取 2 字 bigram
        terms = []
        for t in raw_terms:
            if len(t) <= 4:
                terms.append(t)
            else:
                # 整词也算一个 term
                terms.append(t)
                # 提取 bigram
                for i in range(len(t) - 1):
                    bigram = t[i:i + 2]
                    terms.append(bigram)

        # 去重
        seen = set()
        unique_terms = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)
        terms = unique_terms

        if not terms:
            terms = [query_lower]

        # 3. 逐词条匹配评分
        scored = []
        for entry in all_entries:
            score = 0
            title_lower = entry.title.lower()
            category_lower = entry.category.lower()
            content_lower = entry.content.lower()
            equipment_lower = entry.frontmatter.get("equipment", "").lower()
            tags_lower = [t.lower() for t in entry.tags]

            for term in terms:
                # bigram (2 字) 权重低，长词组权重高
                w = 1 if len(term) <= 2 else 3
                if term in title_lower:
                    score += 10 * w
                if term in category_lower:
                    score += 5 * w
                if any(term in tl for tl in tags_lower):
                    score += 5 * w
                if term in content_lower:
                    score += 2 * w
                if term in equipment_lower:
                    score += 3 * w

            # 完整 query 匹配额外加分
            if query_lower in title_lower:
                score += 30
            if query_lower in content_lower:
                score += 15

            if score > 0:
                meta = entry.to_meta_dict()
                meta["_score"] = score
                meta["content_preview"] = entry.content[:200]
                scored.append(meta)
        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored[:limit]

    def get_categories(self) -> list[str]:
        """返回所有不重复的分类。"""
        cats = set()
        for entry in self._scan_all_files():
            if entry.category:
                cats.add(entry.category)
        return sorted(cats)

    def get_tags(self) -> list[str]:
        """返回所有不重复的标签。"""
        tags = set()
        for entry in self._scan_all_files():
            tags.update(entry.tags)
        return sorted(tags)

    def get_stats(self) -> dict:
        """返回 wiki 统计信息。"""
        all_entries = self._scan_all_files()
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        recent = []
        for entry in all_entries:
            by_type[entry.type] = by_type.get(entry.type, 0) + 1
            by_category[entry.category] = by_category.get(entry.category, 0) + 1
            recent.append(entry.to_meta_dict())
        recent.sort(key=lambda x: x.get("updated", ""), reverse=True)
        return {
            "total_entries": len(all_entries),
            "by_type": by_type,
            "by_category": by_category,
            "recent_updates": recent[:10],
        }

    def is_empty(self) -> bool:
        """检查 wiki 目录是否没有任何词条。"""
        return len(self._scan_all_files()) == 0

    # ------------------------------------------------------------------
    # 索引 / 日志
    # ------------------------------------------------------------------

    def rebuild_index(self):
        """重建 wiki/index.md 索引文件（含一句话摘要）。"""
        all_entries = self._scan_all_files()
        lines = ["# 内容索引\n", f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}，共 {len(all_entries)} 条词条\n"]

        type_labels = {
            "content_summary": "内容摘要",
            "entity": "实体词条",
            "concept": "概念词条",
            "comparative": "对比分析",
            "overview": "总览综述",
        }

        grouped: dict[str, list[WikiEntry]] = {}
        for entry in all_entries:
            grouped.setdefault(entry.type, []).append(entry)

        for etype in WIKI_SUBDIRS:
            full_type = etype if "_" not in etype else etype
            type_name_map = {
                "content": "content_summary",
                "entity": "entity",
                "concept": "concept",
                "comparative": "comparative",
                "overview": "overview",
            }
            full_type = type_name_map.get(etype, etype)
            entries = grouped.get(full_type, [])
            if not entries:
                continue
            label = type_labels.get(full_type, full_type)
            lines.append(f"\n## {label}（{len(entries)} 条）\n")
            for e in sorted(entries, key=lambda x: x.id):
                # 提取正文第一行非标题文本作为摘要
                summary = self._first_prose_line(e.content)
                lines.append(f"- **{e.id}** {e.title} — {summary}")

        with open(os.path.join(self.wiki_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    @staticmethod
    def _first_prose_line(content: str, max_len: int = 120) -> str:
        """提取正文中第一个非标题、非空行的文本段落（截断）。"""
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if len(line) > max_len:
                return line[:max_len] + "..."
            return line
        return ""

    def append_log(self, action: str, detail: str):
        """向 wiki/log.md 追加操作记录。"""
        log_path = os.path.join(self.wiki_dir, "log.md")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_line = f"- **[{timestamp}]** {action} — {detail}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry_line)

    def get_log(self) -> str:
        """读取操作日志内容。"""
        log_path = os.path.join(self.wiki_dir, "log.md")
        if not os.path.exists(log_path):
            return ""
        with open(log_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_index(self) -> str:
        """读取索引文件内容。"""
        idx_path = os.path.join(self.wiki_dir, "index.md")
        if not os.path.exists(idx_path):
            return ""
        with open(idx_path, "r", encoding="utf-8") as f:
            return f.read()

    def backfill_images(self) -> dict:
        """为现有 wiki 词条补录关联图片引用。

        读取 assets/manifest.json 获取 图片→源文件 映射，
        仅将图片追加到同源文件的词条中（幂等）。
        """
        import json as _json

        assets_dir = os.path.join(self.raw_dir, "assets")
        manifest_path = os.path.join(assets_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            return {"updated": 0, "message": "assets/manifest.json 不存在，请先上传含图片的文档"}

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = _json.load(f)

        if not manifest:
            return {"updated": 0, "message": "manifest 为空，无图片映射记录"}

        # 按 source_file 分组图片
        supported_ext = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        images_by_source: dict[str, list[str]] = {}
        for img_name, source in manifest.items():
            if os.path.splitext(img_name)[1].lower() in supported_ext:
                images_by_source.setdefault(source, []).append(img_name)

        # 遍历词条，按 source_file 匹配图片
        all_entries = self._scan_all_files()
        updated = 0
        for entry in all_entries:
            source_file = entry.frontmatter.get("source_file", "")
            if not source_file or source_file == "initial_migration":
                continue
            # 已有图片引用则跳过
            if "## 相关图示" in entry.content:
                continue
            matched_images = images_by_source.get(source_file, [])
            if not matched_images:
                continue
            # 追加图片引用
            img_lines = ["", "## 相关图示", ""]
            for idx, img_name in enumerate(matched_images, 1):
                img_lines.append(f"![图{idx}](/api/knowledge/assets/{img_name})")
            new_content = entry.content.rstrip() + "\n" + "\n".join(img_lines) + "\n"
            if entry.file_path:
                new_text = self._serialize_entry(entry.frontmatter, new_content)
                with open(entry.file_path, "w", encoding="utf-8") as f:
                    f.write(new_text)
                updated += 1

        if updated > 0:
            self.rebuild_index()
            self.append_log("图片补录", f"为 {updated} 条词条追加了图片引用（按源文件匹配）")

        return {"updated": updated, "message": f"已为 {updated} 条词条追加图片引用（按源文件匹配）"}
