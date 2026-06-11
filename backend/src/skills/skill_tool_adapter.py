"""Skill → LangChain Tool 适配器 — 将 SkillDefinition 动态转为 StructuredTool 注入 Agent。"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

from src.skills.skill_models import SkillDefinition

logger = logging.getLogger(__name__)


def _build_args_schema(skill: SkillDefinition) -> type[BaseModel]:
    """从 Skill 的 inputs 定义动态生成 Pydantic 参数模型。"""
    field_definitions: dict[str, Any] = {}
    type_map = {
        "string": (str, ...),
        "number": (float, ...),
        "boolean": (bool, ...),
        "object": (dict, ...),
        "array": (list, ...),
    }

    for inp in skill.metadata.inputs:
        py_type, _ = type_map.get(inp.type, (str, ...))
        if inp.required:
            field_definitions[inp.name] = (py_type, inp.default if inp.default is not None else ...)
        else:
            field_definitions[inp.name] = (py_type | None, inp.default)

    # 保证至少有 query 字段
    if "query" not in field_definitions:
        field_definitions["query"] = (str, "")

    return create_model(f"Skill_{skill.metadata.name}_Args", **field_definitions)


def _build_description(skill: SkillDefinition) -> str:
    """构建 Tool description（LLM 根据此文本决定是否调用）。"""
    parts: list[str] = []
    parts.append(f"[{skill.metadata.skill_type.upper()} Skill] {skill.metadata.description}")

    if skill.metadata.trigger_words:
        parts.append(f"触发词: {', '.join(skill.metadata.trigger_words)}")

    if skill.metadata.inputs:
        descs = [f"  - {i.name} ({i.type}, {'必填' if i.required else '可选'}): {i.description}"
                 for i in skill.metadata.inputs]
        parts.append("输入参数:\n" + "\n".join(descs))

    # SKILL.md body 前 200 字
    if skill.description_md:
        lines = [l for l in skill.description_md.split("\n") if not l.startswith("#")]
        extra = "\n".join(lines).strip()[:200]
        if extra:
            parts.append(f"详细说明: {extra}")

    return "\n".join(parts)


def skill_to_langchain_tool(skill: SkillDefinition, executor) -> StructuredTool:
    """将 SkillDefinition 转为 LangChain StructuredTool。"""
    args_schema = _build_args_schema(skill)
    description = _build_description(skill)
    skill_name = skill.metadata.name

    def _execute(**kwargs) -> str:
        result = executor.execute_sync(skill_name, kwargs)
        return json.dumps(result, ensure_ascii=False, default=str)

    tool = StructuredTool.from_function(
        func=_execute,
        name=f"skill_{skill_name}",
        description=description,
        args_schema=args_schema,
        return_direct=False,
    )
    logger.debug("注册 Skill Tool: %s", tool.name)
    return tool


def register_skills_with_agent(agent, registry, executor) -> list[StructuredTool]:
    """将所有已启用 Skill 注册为 Agent 工具。"""
    tools: list[StructuredTool] = []
    for skill in registry.list_skills(enabled_only=True):
        try:
            tool = skill_to_langchain_tool(skill, executor)
            agent.register_tool(tool)
            tools.append(tool)
            logger.info("Skill '%s' → Tool: %s", skill.metadata.name, tool.name)
        except Exception as e:
            logger.error("注册 Skill '%s' 失败: %s", skill.metadata.name, e)
    return tools
