"""Wiki 生成器 — 使用 LLM 从解析后的文档中提取知识并生成 wiki 词条。"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.knowledge.wiki_manager import WikiManager, WikiEntry
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
8. 若某个设备/部件实体已存在（见下方"已有词条标题"清单），请**复用完全相同的标题**，使后续可识别为同一实体；并在正文内用 `##` 分节区分不同型号/机型各自的参数与概念。同一实体的不同型号差异，写在同一条词条的正文中即可，不要为每个型号单独新建一条实体词条。

## 输出格式
**只输出 JSON 数组本身，不要任何解释、前后缀文字或 markdown 代码块标记。** 每个元素格式如下：
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
        date_str = datetime.now().strftime("%Y-%m-%d")

        # 3. 先处理 content_summary（每份文档独有一条，永不合并），记录摘要 ID 供其他词条引用
        summary_id, summary_title = None, None
        summary_entry = next(
            (e for e in entries_data if e.get("type", "content_summary") == "content_summary"),
            None,
        )
        if summary_entry is not None:
            summary_title = summary_entry.get("title", parsed.title)
            created = self.wiki_manager.create_entry(
                self._base_frontmatter(summary_entry, source_name),
                self._attach_images(summary_entry.get("content", ""), parsed),
                rebuild=False,
            )
            summary_id = created.id
        else:
            logger.warning("LLM 未生成 content_summary，本次入库其他词条将不带摘要关联")

        # 4. 处理其余词条：同实体合并 / 新建，并关联内容摘要
        existing = self.wiki_manager._scan_all_files()  # 复用，避免反复扫描
        created_ids: list[str] = []
        merged_ids: list[str] = []

        for entry_data in entries_data:
            if entry_data is summary_entry:
                continue
            entry_type = entry_data.get("type", "content_summary")
            title = entry_data.get("title", "未命名词条")

            # 仅 entity / concept 参与同实体合并；comparative / overview 等是文档级综合，一律新建
            if entry_type in ("entity", "concept"):
                matched = self.wiki_manager.find_entry_by_title(entry_type, title, existing)
                cur = self.wiki_manager.get_entry(matched.id) if matched else None
                if cur is not None:
                    if f"来源补充：{source_name}" in cur.content:
                        continue  # 本来源已合并过，幂等跳过，不重复新建
                    self._merge_into(cur, entry_data, source_name, date_str, parsed, summary_id, summary_title)
                    merged_ids.append(cur.id)
                    continue

            # 新建路径
            related = [summary_id] if summary_id else []
            frontmatter = self._base_frontmatter(entry_data, source_name)
            frontmatter["related_entries"] = related
            if summary_id:
                frontmatter["source_files"] = [source_name]
            content = self._attach_images(entry_data.get("content", ""), parsed)
            if summary_id:
                content = self._upsert_summary_link(content, summary_id, summary_title)
            entry = self.wiki_manager.create_entry(frontmatter, content, rebuild=False)
            created_ids.append(entry.id)
            existing.append(entry)  # 同文档内若 LLM 产出同标题，后续可互相合并

        # 5. 统一重建索引 + 刷新 ChunkStore（保证合并/新增内容即时可被 RAG 检索）
        self.wiki_manager.rebuild_index()
        cs = self.wiki_manager.chunk_store
        if cs is not None:
            try:
                cs.rebuild_index()
            except Exception as e:
                logger.warning("ChunkStore 刷新失败（不影响入库）: %s", e)

        all_ids = ([summary_id] if summary_id else []) + created_ids + merged_ids
        self.wiki_manager.append_log(
            "文档入库",
            f"文件 {source_name}，新建 {len(created_ids)} 条 / 合并 {len(merged_ids)} 条"
            f"（摘要 {summary_id or '无'}，新建 [{', '.join(created_ids) or '无'}]，"
            f"合并 [{', '.join(merged_ids) or '无'}]）",
        )

        elapsed = round((time.monotonic() - start_time) * 1000)
        return {
            "success": True,
            "source_file": source_name,
            "entries_created": len(created_ids),
            "entries_merged": len(merged_ids),
            "entry_ids": all_ids,
            "processing_time_ms": elapsed,
            "message": (
                f"文档处理完成：新建 {len(created_ids)} 条，合并 {len(merged_ids)} 条 wiki 词条"
            ),
        }

    # ------------------------------------------------------------------
    # process_document 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _base_frontmatter(entry_data: dict, source_name: str) -> dict:
        """从 LLM 输出构建写入用的基础 frontmatter。"""
        return {
            "type": entry_data.get("type", "content_summary"),
            "title": entry_data.get("title", "未命名词条"),
            "category": entry_data.get("category", "整机"),
            "tags": entry_data.get("tags", []),
            "equipment": entry_data.get("equipment", ""),
            "severity": entry_data.get("severity", ""),
            "source_file": source_name,
            "concept_subcategory": entry_data.get("concept_subcategory"),
        }

    @staticmethod
    def _attach_images(content: str, parsed: ParsedDocument) -> str:
        """在正文末尾追加来源文档的图片引用段落（幂等：已有则跳过）。"""
        if not parsed.images or "## 相关图示" in content:
            return content
        img_lines = ["", "## 相关图示", ""]
        for idx, img_name in enumerate(parsed.images, 1):
            img_lines.append(f"![图{idx}](/api/knowledge/assets/{img_name})")
        return content.rstrip() + "\n" + "\n".join(img_lines) + "\n"

    def _merge_into(
        self,
        cur: WikiEntry,
        entry_data: dict,
        source_name: str,
        date_str: str,
        parsed: ParsedDocument,
        summary_id: Optional[str],
        summary_title: Optional[str],
    ) -> None:
        """把新文档的同一实体内容作为「来源补充」分节追加到已有词条。

        调用方需保证 cur 是最新读取的词条，且尚未含本来源的分节标记（幂等性由调用方判定）。
        """
        section_marker = f"来源补充：{source_name}"
        body = entry_data.get("content", "").strip()
        new_section = f"\n\n## {section_marker}（{date_str}）\n\n{body}"
        if parsed.images:
            img_lines = ["", "### 相关图示", ""]
            for idx, img_name in enumerate(parsed.images, 1):
                img_lines.append(f"![图{idx}](/api/knowledge/assets/{img_name})")
            new_section += "\n" + "\n".join(img_lines)

        new_content = cur.content.rstrip() + new_section + "\n"
        if summary_id:
            new_content = self._upsert_summary_link(new_content, summary_id, summary_title)

        # 合并 frontmatter
        cur_fm = cur.frontmatter
        merged_tags = list(dict.fromkeys((cur_fm.get("tags") or []) + (entry_data.get("tags") or [])))
        equipment = cur_fm.get("equipment") or entry_data.get("equipment") or ""
        base_sources = cur_fm.get("source_files")
        if not base_sources:
            base_sources = [cur_fm["source_file"]] if cur_fm.get("source_file") else []
        source_files = list(dict.fromkeys(base_sources + [source_name]))
        related = list(dict.fromkeys((cur_fm.get("related_entries") or []) + ([summary_id] if summary_id else [])))

        fm_updates = {
            "tags": merged_tags,
            "equipment": equipment,
            "source_files": source_files,
            "related_entries": related,
        }
        self.wiki_manager.update_entry(cur.id, fm_updates, new_content, rebuild=False)

    @staticmethod
    def _upsert_summary_link(content: str, summary_id: str, summary_title: str) -> str:
        """在正文维护「## 关联内容摘要」章节，幂等加入指向摘要词条的内部链接。"""
        link = f"[[{summary_id} {summary_title}]]"
        header = "## 关联内容摘要"
        if f"[[{summary_id} " in content:  # 已存在该摘要链接
            return content
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == header:
                insert_at = i + 1
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
                lines.insert(insert_at, link)
                return "\n".join(lines)
        # 尚无该章节：追加到末尾
        return content.rstrip() + f"\n\n{header}\n\n{link}\n"

    async def _generate_entries(self, parsed: ParsedDocument, source_name: str) -> list[dict]:
        """调用 LLM 生成 wiki 词条数据。"""
        # 截断过长文本
        doc_text = parsed.text
        max_chars = 15000
        if len(doc_text) > max_chars:
            doc_text = doc_text[:max_chars] + "\n\n...[文档内容已截断]"

        # 注入已有实体/概念词条标题，引导 LLM 复用相同标题（便于后续同实体合并）
        existing_titles = self._existing_mergeable_titles()
        existing_block = ""
        if existing_titles:
            existing_block = (
                "\n--- 已有词条标题（若本文档涉及其中实体，请复用完全相同的标题） ---\n"
                + "\n".join(f"- {t}" for t in existing_titles)
                + "\n--- 已有词条标题结束 ---\n"
            )

        user_message = f"""请分析以下燃气轮机技术文档，提取知识并生成维基词条。

文档标题：{parsed.title}
文件名：{source_name}
{existing_block}
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

    def _existing_mergeable_titles(self) -> list[str]:
        """返回已存在的实体/概念词条标题（仅这两类参与同实体合并）。"""
        titles = []
        for e in self.wiki_manager._scan_all_files():
            if e.type in ("entity", "concept") and e.title:
                titles.append(e.title)
        return titles

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
