"""Skill 执行引擎 — HTTP / Dataset / Workflow / Python / Shell / DB 六种执行后端 + 沙箱隔离。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from src.skills.skill_models import SkillDefinition, SkillMetadata

logger = logging.getLogger(__name__)


class SkillExecutor:
    """执行已注册的 Skill，按 skill_type 分发到对应后端。"""

    def __init__(
        self,
        registry,  # SkillRegistry
        wiki_manager=None,
        workflow_store: dict | None = None,
    ):
        self._registry = registry
        self._wiki_manager = wiki_manager
        self._workflow_store = workflow_store or {}
        self._llm = None  # 懒加载，供 prompt injection 使用

    def set_workflow_store(self, store: dict):
        self._workflow_store = store

    # ---- 公开接口 ----

    def execute_sync(self, skill_name: str, args: dict[str, Any]) -> dict:
        """同步执行（供 LangChain Tool / workflow 调用）。"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return loop.run_in_executor(pool, self._execute_in_new_loop, skill_name, args).result()
            else:
                return loop.run_until_complete(self.execute(skill_name, args))
        except RuntimeError:
            return asyncio.run(self.execute(skill_name, args))

    async def execute(self, skill_name: str, args: dict[str, Any]) -> dict:
        """异步执行 Skill。"""
        skill = self._registry.get_skill(skill_name)
        if skill is None:
            return {"status": "error", "error": f"Skill '{skill_name}' 不存在"}
        if not skill.metadata.enabled:
            return {"status": "error", "error": f"Skill '{skill_name}' 已禁用"}

        meta = skill.metadata
        start = time.monotonic()

        # 渐进式加载 references（按需）
        refs = self._registry.load_references(skill_name)

        # 加载 assets
        assets = self._registry.get_assets(skill_name)

        try:
            # 如果 execution 为空（纯提示型 skill），走 LLM 上下文注入
            if not meta.execution:
                result = await self._execute_prompt_injection(skill, args, refs, assets)
            else:
                dispatch = {
                    "http": self._execute_http,
                    "dataset": self._execute_dataset,
                    "workflow": self._execute_workflow,
                    "python": self._execute_python,
                    "shell": self._execute_shell,
                    "db": self._execute_db,
                }
                handler = dispatch.get(meta.skill_type)
                if handler is None:
                    return {"status": "error", "error": f"不支持的 skill_type: {meta.skill_type}"}
                result = await handler(meta, args, refs)

            elapsed = round((time.monotonic() - start) * 1000)
            return {"status": "success", "data": result, "elapsed_ms": elapsed, "skill": skill_name}

        except subprocess.TimeoutExpired:
            elapsed = round((time.monotonic() - start) * 1000)
            return {"status": "error", "error": f"执行超时（{meta.timeout}s）", "elapsed_ms": elapsed, "skill": skill_name}
        except Exception as e:
            elapsed = round((time.monotonic() - start) * 1000)
            logger.error("Skill '%s' 执行失败: %s", skill_name, e)
            return {"status": "error", "error": str(e), "elapsed_ms": elapsed, "skill": skill_name}

    def _execute_in_new_loop(self, skill_name: str, args: dict) -> dict:
        return asyncio.run(self.execute(skill_name, args))

    # ==================================================================
    # Prompt Injection — 纯提示型 Skill（无 execution 配置）
    # 将 SKILL.md 全文 + references + assets 注入 LLM 上下文
    # ==================================================================

    async def _execute_prompt_injection(
        self, skill: SkillDefinition, args: dict, refs: dict, assets: dict,
    ) -> Any:
        """纯提示型 Skill：将 skill 的完整文档注入 LLM 上下文生成回答。"""
        query = args.get("query", args.get("input", ""))

        # 组装上下文
        context_parts: list[str] = []
        context_parts.append(f"# Skill: {skill.metadata.name}")
        context_parts.append(f"描述: {skill.metadata.description}")
        if skill.metadata.trigger_words:
            context_parts.append(f"触发词: {', '.join(skill.metadata.trigger_words)}")
        context_parts.append("")

        # SKILL.md body
        if skill.description_md:
            context_parts.append("## Skill 指令文档")
            context_parts.append(skill.description_md)
            context_parts.append("")

        # References
        if refs:
            context_parts.append("## 参考资源")
            for ref_name, ref_content in refs.items():
                context_parts.append(f"### {ref_name}")
                context_parts.append(ref_content[:3000])  # 每个参考最多 3000 字
                context_parts.append("")

        # Assets
        if assets:
            context_parts.append("## 预加载资源")
            for asset_name, asset_content in assets.items():
                context_parts.append(f"### {asset_name}")
                context_parts.append(asset_content[:3000])
                context_parts.append("")

        skill_context = "\n".join(context_parts)

        # 调用 LLM
        if self._llm is None:
            # 尝试初始化 LLM
            try:
                from src.config import get_settings
                from langchain_openai import ChatOpenAI
                settings = get_settings()
                self._llm = ChatOpenAI(
                    base_url=settings.active_llm_base_url,
                    api_key=settings.active_llm_api_key,
                    model=settings.active_llm_model_name,
                    temperature=0.3, timeout=120, max_retries=1,
                )
            except Exception:
                return {
                    "answer": skill_context,
                    "note": "LLM 不可用，已返回 Skill 完整文档作为上下文参考",
                }

        from langchain_core.messages import SystemMessage, HumanMessage
        system_msg = SystemMessage(content=(
            f"你是一个已激活的 Agent 技能 '{skill.metadata.name}'。\n"
            f"以下是该技能的完整指令文档和参考资料，请严格按照其中的流程和规范来回答用户问题。\n\n"
            f"{skill_context}"
        ))
        user_msg = HumanMessage(content=query)

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._llm.invoke([system_msg, user_msg])
            )
            return {"answer": response.content, "skill": skill.metadata.name, "mode": "prompt_injection"}
        except Exception as e:
            return {
                "answer": skill_context,
                "error": f"LLM 调用失败: {e}",
                "note": "已返回 Skill 文档作为替代",
            }

    # ==================================================================
    # HTTP 后端
    # ==================================================================

    async def _execute_http(self, meta: SkillMetadata, args: dict, refs: dict) -> Any:
        cfg = meta.get_http_config()
        url = self._render_template(cfg.url, args)
        rendered_params = {k: self._render_template(v, args) for k, v in cfg.query_params.items()}

        body = None
        if cfg.body_template:
            body = self._render_template(cfg.body_template, args)

        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            resp = await client.request(
                method=cfg.method, url=url,
                headers=cfg.headers, params=rendered_params or None,
                content=body,
            )
            resp.raise_for_status()

        try:
            data = resp.json()
        except Exception:
            return {"raw": resp.text}

        if cfg.response_path:
            data = self._extract_path(data, cfg.response_path)
        return data

    # ==================================================================
    # Dataset 后端 — 复用 WikiManager/ChunkStore 混合检索
    # ==================================================================

    async def _execute_dataset(self, meta: SkillMetadata, args: dict, refs: dict) -> Any:
        cfg = meta.get_dataset_config()
        query = self._render_template(cfg.query_template, args) or args.get("query", "")

        if self._wiki_manager is None:
            return {"query": query, "total": 0, "items": [], "error": "知识库未初始化"}

        chunk_store = self._wiki_manager.chunk_store
        if chunk_store is None:
            entries = self._wiki_manager.search_entries(query, top_k=cfg.top_k)
            return {"query": query, "total": len(entries), "items": [
                {"title": e.get("title", ""), "category": e.get("category", ""),
                 "content": e.get("content", "")[:500]}
                for e in entries
            ]}

        results = chunk_store.search(query, top_k=cfg.top_k)
        return {"query": query, "total": len(results), "items": [
            {"title": r.get("title", ""), "content": r.get("content", "")[:500],
             "score": r.get("score", 0), "source": r.get("source", "")}
            for r in results
        ]}

    # ==================================================================
    # Workflow 后端 — 嵌套调用工作流
    # ==================================================================

    async def _execute_workflow(self, meta: SkillMetadata, args: dict, refs: dict) -> Any:
        cfg = meta.get_workflow_config()
        from src.core.workflow_engine import execute_workflow

        wf_def = self._workflow_store.get(cfg.workflow_id)
        if wf_def is None:
            from src.core.workflow_engine import TEMPLATES
            wf_def = next((t for t in TEMPLATES if t["id"] == cfg.workflow_id), None)
        if wf_def is None:
            return {"error": f"工作流 '{cfg.workflow_id}' 不存在"}

        user_input = args.get(cfg.pass_input_as, args.get("query", ""))
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, execute_workflow, wf_def, user_input)

    # ==================================================================
    # Python 后端 — subprocess 沙箱
    # ==================================================================

    async def _execute_python(self, meta: SkillMetadata, args: dict, refs: dict) -> Any:
        cfg = meta.get_python_config()
        skill_dir = Path(
            self._registry.get_skill(meta.name).skill_dir
            if self._registry.get_skill(meta.name) else "."
        )
        script_path = skill_dir / cfg.script
        if not script_path.exists():
            return {"error": f"脚本不存在: {cfg.script}"}

        cmd = [cfg.interpreter, str(script_path)]
        return await self._run_subprocess(cmd, skill_dir, args, cfg.env_vars, meta.timeout, refs)

    # ==================================================================
    # Shell 后端 — subprocess 沙箱
    # ==================================================================

    async def _execute_shell(self, meta: SkillMetadata, args: dict, refs: dict) -> Any:
        cfg = meta.get_shell_config()
        skill_dir = Path(
            self._registry.get_skill(meta.name).skill_dir
            if self._registry.get_skill(meta.name) else "."
        )
        script_path = skill_dir / cfg.script
        if not script_path.exists():
            return {"error": f"脚本不存在: {cfg.script}"}

        cmd = [cfg.interpreter, str(script_path)]
        return await self._run_subprocess(cmd, skill_dir, args, cfg.env_vars, meta.timeout, refs)

    # ==================================================================
    # DB 后端 — 只读查询
    # ==================================================================

    async def _execute_db(self, meta: SkillMetadata, args: dict, refs: dict) -> Any:
        cfg = meta.get_db_config()
        query = self._render_template(cfg.query, args)

        try:
            import sqlite3
            conn = sqlite3.connect(cfg.connection_string)
            conn.row_factory = sqlite3.Row
            if cfg.readonly:
                cursor = conn.execute("BEGIN")
                conn.execute("PRAGMA query_only = ON")
            cursor = conn.execute(query)
            rows = cursor.fetchmany(cfg.max_rows)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()
            return {
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows],
                "row_count": len(rows),
            }
        except Exception as e:
            return {"error": f"数据库查询失败: {e}"}

    # ==================================================================
    # 沙箱 subprocess 核心
    # ==================================================================

    async def _run_subprocess(
        self,
        cmd: list[str],
        cwd: Path,
        args: dict,
        extra_env: dict[str, str],
        timeout: int,
        refs: dict,
    ) -> dict:
        """沙箱执行脚本：subprocess 隔离 + 超时控制 + 受限环境。"""
        env = {
            "SKILL_ARGS": json.dumps(args, ensure_ascii=False),
            "SKILL_REFS": json.dumps(
                {k: v[:2000] for k, v in refs.items()}, ensure_ascii=False
            ),
            "PYTHONPATH": str(cwd),
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
            **extra_env,
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, cwd=str(cwd), env=env,
                capture_output=True, text=True,
                timeout=timeout,
            ),
        )

        stdout = result.stdout[:10000]
        stderr = result.stderr[:5000]

        # 尝试解析 stdout 为 JSON
        output: Any = stdout
        try:
            output = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "exit_code": result.returncode,
            "output": output,
            "stderr": stderr if result.returncode != 0 else "",
        }

    # ---- 工具方法 ----

    @staticmethod
    def _render_template(template: str, context: dict) -> str:
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    @staticmethod
    def _extract_path(data: Any, path: str) -> Any:
        current = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current
