"""Wiki 生成器 — 使用 LLM 从解析后的文档中提取知识并生成 wiki 词条。"""

import json
import logging
import os
import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.knowledge.wiki_manager import WikiManager
from src.knowledge.document_parser import ParsedDocument

logger = logging.getLogger(__name__)

WIKI_GENERATION_SYSTEM_PROMPT = """你是一个燃气轮机运维知识库管理专家。你的任务是从一份技术文档中提取知识，生成维基词条。

## 维基词条类型
- content_summary: 文档核心内容的摘要条目（每份文档必须有 1 条）
- entity: 设备、组件等实体条目（如"燃气轮机"、"燃烧室"、"透平机"、"发电机"、"余热锅炉"、"控制系统"、"整机"、"辅助系统"等大型设备或组件，或"压气机叶片"、"DLN燃烧器"、"余热锅炉管束"、"水洗系统"、"冷却系统"等小型零部件或系统）
- concept: 概念条目，包括参数指标、操作规程、技术方法、报警规则、设计规则等
- comparative: 对比分析条目（如不同清洗方法对比、不同检测标准对比）
- overview: 综述性条目，对某一主题的全景概述

## 要求
1. 每份文档最多生成不超过 20 条维基词条
2. 第一条必须是 content_summary 类型，概括文档核心内容
3. 每条目需有清晰的标题、分类、标签
4. 内容用 markdown 格式，包含 ## 标题分节，内容充实专业
5. 标签要具体，便于后续检索
6. 从文档中提取所有提到的设备、部件、技术概念作为独立词条
7. 对于涉及规程/标准的部分，提炼为 concept 类型词条
8. 对于相同的实体，但是型号不同，产生了新的技术概念，在原有的词条内容上新增，并区别不同型号设备的概念

## 输出格式
请输出 JSON 数组，每个元素格式如下（不要输出其他内容，只输出 JSON）：
```json
[
  {
    "type": "content_summary",
    "title": "条目标题",
    "category": "分类（如：压气机、燃烧室、透平、发电机、余热锅炉、控制系统、整机、辅助系统）",
    "tags": ["标签1", "标签2"],
    "equipment": "关联设备（如有）",
    "severity": "高|中|低（如有）",
    "concept_subcategory": null,
    "content": "markdown 格式的条目正文"
  }
]
```

concept_subcategory 仅在 type 为 concept 时填写，可选值：参数、指标、规程、方案、技术、报警规则、设计规则。"""


class WikiGenerator:
    """LLM 驱动的 wiki 词条生成器。"""

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
            timeout=180,
            max_retries=1,
        )

    async def process_document(self, file_path: str, parsed: ParsedDocument) -> dict:
        """完整文档入库流程：解析 → 生成词条 → 写入文件 → 更新索引。

        Returns:
            处理结果摘要 dict
        """
        start_time = time.monotonic()
        source_name = os.path.basename(file_path)

        # 1. 将解析后的 markdown 保存到 raw/
        md_path = os.path.join(
            self.wiki_manager.raw_dir,
            os.path.splitext(source_name)[0] + ".md",
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {parsed.title}\n\n来源文件: {source_name}\n\n{parsed.text}")

        # 2. 调用 LLM 生成词条
        entries_data = await self._generate_entries(parsed, source_name)

        # 3. 写入 wiki 文件
        created_entries = []
        for entry_data in entries_data:
            frontmatter = {
                "type": entry_data.get("type", "content_summary"),
                "title": entry_data.get("title", "未命名词条"),
                "category": entry_data.get("category", "整机"),
                "tags": entry_data.get("tags", []),
                "equipment": entry_data.get("equipment", ""),
                "severity": entry_data.get("severity", ""),
                "source_file": source_name,
                "concept_subcategory": entry_data.get("concept_subcategory"),
            }
            content = entry_data.get("content", "")
            # 追加图片引用段落
            if parsed.images:
                img_lines = ["", "## 相关图示", ""]
                for idx, img_name in enumerate(parsed.images, 1):
                    img_lines.append(f"![图{idx}](/api/knowledge/assets/{img_name})")
                content += "\n".join(img_lines)
            entry = self.wiki_manager.create_entry(frontmatter, content)
            created_entries.append(entry.id)

        # 4. 更新索引和日志
        self.wiki_manager.rebuild_index()
        self.wiki_manager.append_log(
            "文档入库",
            f"文件 {source_name}，生成 {len(created_entries)} 条词条 ({', '.join(created_entries)})",
        )

        elapsed = round((time.monotonic() - start_time) * 1000)
        return {
            "success": True,
            "source_file": source_name,
            "entries_created": len(created_entries),
            "entry_ids": created_entries,
            "processing_time_ms": elapsed,
            "message": f"文档处理完成，生成 {len(created_entries)} 条 wiki 词条",
        }

    async def _generate_entries(self, parsed: ParsedDocument, source_name: str) -> list[dict]:
        """调用 LLM 生成 wiki 词条数据。"""
        # 截断过长文本
        doc_text = parsed.text
        max_chars = 15000
        if len(doc_text) > max_chars:
            doc_text = doc_text[:max_chars] + "\n\n...[文档内容已截断]"

        user_message = f"""请分析以下燃气轮机技术文档，提取知识并生成维基词条。

文档标题：{parsed.title}
文件名：{source_name}

--- 文档内容 ---
{doc_text}
--- 文档结束 ---

请生成 10-15 条维基词条，以 JSON 数组格式输出。"""

        try:
            response = self._llm.invoke([
                SystemMessage(content=WIKI_GENERATION_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ])
            content = response.content
            # 提取 JSON 部分
            entries = self._parse_llm_response(content)
            return entries
        except Exception as e:
            logger.error("LLM 生成 wiki 词条失败: %s", e)
            # 降级：生成一条基础摘要词条
            return [{
                "type": "content_summary",
                "title": parsed.title,
                "category": "整机",
                "tags": [parsed.title],
                "equipment": "",
                "severity": "",
                "concept_subcategory": None,
                "content": f"## 概述\n\n{parsed.text[:2000]}\n\n> 此词条由系统自动降级生成（LLM 调用失败）。",
            }]

    def _parse_llm_response(self, content: str) -> list[dict]:
        """解析 LLM 返回的 JSON，兼容 markdown 代码块包裹。"""
        # 尝试提取 ```json ... ``` 中的内容
        json_match = content
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_match = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                json_match = content[start:end].strip()

        try:
            result = json.loads(json_match)
            if isinstance(result, list):
                return result
            return [result]
        except json.JSONDecodeError:
            logger.warning("LLM 返回非 JSON 格式，尝试修复...")
            # 尝试更宽松的提取
            bracket_start = json_match.find("[")
            bracket_end = json_match.rfind("]")
            if bracket_start != -1 and bracket_end > bracket_start:
                try:
                    return json.loads(json_match[bracket_start:bracket_end + 1])
                except json.JSONDecodeError:
                    pass
            logger.error("无法解析 LLM 返回的 JSON")
            return []
