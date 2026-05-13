"""Wiki 问答服务 — 基于 wiki 词条的检索增强问答。"""

import logging
import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.knowledge.wiki_manager import WikiManager

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """你是一个燃气轮机运维知识库问答专家。请基于提供的知识库词条内容回答用户问题。

## 回答规则
1. 基于提供的词条内容回答，不要编造信息
2. 在回答中标注来源，格式：[来源: 词条ID 标题]
3. 如果提供的词条不足以回答问题，如实说明并建议补充相关资料
4. 对于根因分析类问题，给出因果推理追溯链
5. 使用清晰的 markdown 格式，善用列表、表格等结构化表达"""


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

        Returns:
            {"answer": str, "citations": list[dict], "processing_time_ms": int}
        """
        start_time = time.monotonic()

        # 1. 检索相关词条
        related = self.wiki_manager.search_entries(query, limit=8)
        if not related:
            elapsed = round((time.monotonic() - start_time) * 1000)
            return {
                "answer": "知识库中暂无与您的问题相关的词条。请先上传相关技术文档，系统会自动提取知识。",
                "citations": [],
                "processing_time_ms": elapsed,
            }

        # 2. 读取完整词条内容
        contexts = []
        citations = []
        for meta in related:
            entry = self.wiki_manager.get_entry(meta["id"])
            if not entry:
                continue
            # 截取相关片段
            snippet = self._extract_relevant_snippet(entry.content, query)
            contexts.append(f"### 词条 {entry.id}: {entry.title}\n类型: {entry.type} | 分类: {entry.category}\n\n{snippet}")
            citations.append({
                "entry_id": entry.id,
                "title": entry.title,
                "type": entry.type,
                "category": entry.category,
                "relevance_score": meta.get("_score", 0),
                "snippet": snippet[:300],
            })

        # 3. 构建 prompt 并调用 LLM
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
            logger.error("Wiki QA LLM 调用失败: %s", e)
            answer = f"LLM 服务暂时不可用（{e}），以下是与您问题相关的知识库词条：\n\n"
            for c in citations:
                answer += f"- **{c['entry_id']}** {c['title']}\n"

        elapsed = round((time.monotonic() - start_time) * 1000)
        return {
            "answer": answer,
            "citations": citations,
            "processing_time_ms": elapsed,
        }

    @staticmethod
    def _extract_relevant_snippet(content: str, query: str, max_length: int = 1000) -> str:
        """从词条内容中提取与 query 最相关的片段。"""
        if len(content) <= max_length:
            return content

        query_terms = query.lower().split()
        best_pos = 0
        best_score = 0

        # 滑动窗口找最相关的段落
        step = 200
        for pos in range(0, len(content) - max_length, step):
            window = content[pos:pos + max_length].lower()
            score = sum(window.count(t) for t in query_terms)
            if score > best_score:
                best_score = score
                best_pos = pos

        snippet = content[best_pos:best_pos + max_length]
        if best_pos > 0:
            snippet = "..." + snippet
        if best_pos + max_length < len(content):
            snippet = snippet + "..."
        return snippet
