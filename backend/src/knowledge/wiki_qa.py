"""Wiki 问答服务 — 基于索引匹配 + 词条内容检索的问答。

查询流程：
  1. 读取 index.md（全 wiki 的目录 + 一句话摘要）
  2. LLM 从索引中匹配与 query 相关的词条 ID
  3. 读取匹配词条的完整内容 + 跟随 [[xxx]] 内部链接
  4. LLM 综合所有内容生成回答，标注来源
"""

import logging
import re
import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.knowledge.wiki_manager import WikiManager

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """你是燃气轮机运维知识库问答专家。请基于提供的知识库词条内容回答用户问题。

## 回答规则
1. 基于提供的词条内容回答，不要编造信息
2. 在回答中标注来源，格式：[来源: 词条ID 标题]
3. 如果提供的词条不足以回答问题，如实说明并建议补充相关资料
4. 对于根因分析类问题，给出因果推理追溯链
5. 使用清晰的 markdown 格式，善用列表、表格等结构化表达"""

# Step 2: LLM 从索引中匹配相关词条 ID
MATCH_PROMPT = """你是一个知识库检索助手。下面是知识库的完整索引（每条包含 ID、标题、摘要）。

## 知识库索引

{index}

## 用户问题
{query}

## 任务
从索引中找出与用户问题相关的词条。返回格式：每行一个词条 ID（如 W001），不要其他内容。
如果没有相关词条，回复 NONE。"""


class WikiQA:
    """基于 wiki 词条的知识问答。"""

    def __init__(self, wiki_manager: WikiManager):
        self.wiki_manager = wiki_manager
        self._llm = self._create_llm()

    def _create_llm(self) -> ChatOpenAI:
        settings = get_settings()
        return ChatOpenAI(
            base_url=settings.active_llm_base_url,
            api_key=settings.active_llm_api_key,
            model=settings.active_llm_model_name,
            temperature=0.3,
            timeout=120,
            max_retries=1,
        )

    async def answer(self, query: str) -> dict:
        """基于 wiki 知识库回答问题。

        流程：读索引 → LLM 匹配词条 → 读页面内容 + 跟随链接 → LLM 生成回答
        """
        start_time = time.monotonic()

        # ── Step 1: 读取 index.md ──
        index_content = self.wiki_manager.get_index()
        if not index_content or len(index_content) < 50:
            elapsed = round((time.monotonic() - start_time) * 1000)
            return {
                "answer": "知识库索引为空，请先上传技术文档。",
                "citations": [],
                "processing_time_ms": elapsed,
            }

        # ── Step 2: 混合检索匹配词条（BM25+Embedding+RRF），LLM 索引匹配作为 fallback ──
        results = self.wiki_manager.search_entries(query, limit=5, use_hybrid=True)
        matched_ids = [r.get("entry_id") or r.get("id") for r in results]

        if not matched_ids:
            # Fallback: LLM 从索引中匹配
            try:
                match_response = self._llm.invoke([
                    HumanMessage(content=MATCH_PROMPT.format(index=index_content, query=query)),
                ])
                matched_ids = self._parse_matched_ids(match_response.content)
            except Exception as e:
                logger.warning("LLM 索引匹配也失败: %s", e)

        if not matched_ids:
            elapsed = round((time.monotonic() - start_time) * 1000)
            return {
                "answer": "知识库中暂无与您的问题相关的词条。请先上传相关技术文档，系统会自动提取知识。",
                "citations": [],
                "processing_time_ms": elapsed,
            }

        # ── Step 3: 读取匹配词条内容 + 跟随 [[xxx]] 链接 ──
        contexts, citations = self._load_entries_with_links(matched_ids)

        if not contexts:
            elapsed = round((time.monotonic() - start_time) * 1000)
            return {
                "answer": "匹配到词条但无法读取内容，请检查知识库状态。",
                "citations": [],
                "processing_time_ms": elapsed,
            }

        # ── Step 4: LLM 综合回答 ──
        context_text = "\n\n---\n\n".join(contexts)
        user_message = f"""## 知识库参考资料

{context_text}

---

## 用户问题
{query}

请基于以上知识库词条内容回答问题，并标注来源。"""

        try:
            response = self._llm.invoke([
                SystemMessage(content=QA_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ])
            answer = response.content
        except Exception as e:
            logger.error("Wiki QA LLM 回答生成失败: %s", e)
            answer = f"LLM 服务暂时不可用（{e}），以下是与您问题相关的知识库词条：\n\n"
            for c in citations:
                answer += f"- **{c['entry_id']}** {c['title']}\n"

        elapsed = round((time.monotonic() - start_time) * 1000)
        return {
            "answer": answer,
            "citations": citations,
            "processing_time_ms": elapsed,
        }

    def _parse_matched_ids(self, llm_response: str) -> list[str]:
        """从 LLM 回复中解析词条 ID 列表。"""
        ids = []
        for line in llm_response.strip().split("\n"):
            line = line.strip()
            if line.upper() == "NONE" or not line:
                continue
            # 提取 W### 格式的 ID
            match = re.search(r"(W\d+)", line)
            if match:
                ids.append(match.group(1))
        # 去重，保持顺序
        seen = set()
        unique = []
        for eid in ids:
            if eid not in seen:
                seen.add(eid)
                unique.append(eid)
        return unique[:8]

    def _load_entries_with_links(self, entry_ids: list[str]) -> tuple[list[str], list[dict]]:
        """加载词条内容，并跟随 [[xxx]] 内部链接加载关联词条。"""
        contexts = []
        citations = []
        seen_ids = set()

        def load_entry(eid: str, depth: int = 0):
            if eid in seen_ids or depth > 1:
                return
            entry = self.wiki_manager.get_entry(eid)
            if not entry:
                return
            seen_ids.add(eid)

            contexts.append(
                f"### 词条 {entry.id}: {entry.title}\n"
                f"类型: {entry.type} | 分类: {entry.category}\n\n{entry.content}"
            )
            citations.append({
                "entry_id": entry.id,
                "title": entry.title,
                "type": entry.type,
                "category": entry.category,
            })

            # 提取 [[xxx]] 链接并跟随
            for link_match in re.finditer(r"\[\[(W\d+)", entry.content):
                linked_id = link_match.group(1)
                load_entry(linked_id, depth + 1)

        for eid in entry_ids:
            load_entry(eid)

        return contexts, citations
