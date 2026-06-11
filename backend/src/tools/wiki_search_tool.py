"""Wiki 知识库搜索工具 — 检索技术知识库中的相关词条。"""

import json
import os
from langchain_core.tools import tool


def _get_wiki_manager():
    from src.knowledge.wiki_manager import WikiManager
    knowledge_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "knowledge"))
    return WikiManager(knowledge_root)


@tool
def wiki_search(query: str) -> str:
    """搜索技术知识库，检索与关键词匹配的 wiki 词条。

    当用户询问燃机技术问题、检维修规程、故障处理方案、设备参数说明等知识性问题时使用此工具。
    返回匹配词条的标题、分类、标签和内容摘要。

    Args:
        query: 搜索关键词或问题描述
    """
    wiki_mgr = _get_wiki_manager()
    try:
        results = wiki_mgr.search_entries(query, limit=8, use_hybrid=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("wiki_search failed: %s", e)
        return json.dumps({"total": 0, "message": "检索服务失败，请稍后重试", "error": str(e)}, ensure_ascii=False)

    if not results:
        return json.dumps({"total": 0, "message": "未找到相关知识词条"}, ensure_ascii=False)

    items = []
    for r in results:
        entry_id = r.get("entry_id") or r.get("id")
        # 混合检索结果已含 content 和 heading；bigram 结果需单独加载
        if "content" in r and r.get("heading") is not None:
            content_preview = r["content"][:500]
            heading = r.get("heading", "")
        else:
            entry = wiki_mgr.get_entry(entry_id)
            content_preview = entry.content[:500] if entry else ""
            heading = ""
        items.append({
            "id": entry_id,
            "title": r["title"],
            "type": r["type"],
            "category": r["category"],
            "tags": r.get("tags", []),
            "severity": r.get("severity", ""),
            "heading": heading,
            "score": r.get("score", r.get("_score", 0)),
            "content_preview": content_preview,
        })

    return json.dumps({"total": len(items), "items": items}, ensure_ascii=False, indent=2)
