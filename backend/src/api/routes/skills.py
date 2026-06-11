"""Skill 管理 API — CRUD、执行、校验、类型定义、渐进加载、ZIP 导入导出、文件编辑。"""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from src.skills.skill_models import (
    SkillCreateRequest,
    SkillExecuteRequest,
    SkillUpdateRequest,
)

router = APIRouter()


@router.get("/list")
async def list_skills(request: Request):
    """列出所有已注册 Skill。"""
    registry = request.app.state.skill_registry
    return [
        {
            "name": s.metadata.name,
            "version": s.metadata.version,
            "description": s.metadata.description,
            "skill_type": s.metadata.skill_type,
            "trigger_words": s.metadata.trigger_words,
            "inputs": [i.model_dump() for i in s.metadata.inputs],
            "outputs": [o.model_dump() for o in s.metadata.outputs],
            "execution": s.metadata.execution,
            "enabled": s.metadata.enabled,
            "timeout": s.metadata.timeout,
            "sandbox": s.metadata.sandbox,
        }
        for s in registry.list_skills()
    ]


@router.get("/types")
async def get_skill_types():
    """返回支持的 Skill 类型及配置 Schema。"""
    return {"types": [
        {"value": "http", "label": "HTTP 接口", "description": "对接外部 RESTful API",
         "execution_schema": {"url": "string (必填)", "method": "GET|POST|PUT|DELETE|PATCH",
                              "headers": "dict", "query_params": "dict", "body_template": "string",
                              "timeout": "number", "response_path": "string (dot-path)"}},
        {"value": "dataset", "label": "知识库检索", "description": "基于知识库问答与检索",
         "execution_schema": {"source": "wiki|chunk_store", "query_template": "string",
                              "top_k": "number", "use_hybrid": "boolean"}},
        {"value": "workflow", "label": "工作流编排", "description": "嵌套调用已保存的工作流",
         "execution_schema": {"workflow_id": "string (必填)", "pass_input_as": "string"}},
        {"value": "python", "label": "Python 脚本", "description": "沙箱执行 Python 脚本",
         "execution_schema": {"script": "string (scripts/main.py)", "interpreter": "python|python3",
                              "env_vars": "dict"}},
        {"value": "shell", "label": "Shell 脚本", "description": "沙箱执行 Shell/Bash 脚本",
         "execution_schema": {"script": "string (scripts/run.sh)", "interpreter": "bash|sh",
                              "env_vars": "dict"}},
        {"value": "db", "label": "数据库查询", "description": "参数化 SQL 查询（只读）",
         "execution_schema": {"connection_string": "string (必填)", "query": "string (SQL)",
                              "readonly": "boolean", "max_rows": "number"}},
    ]}


@router.get("/{skill_name}")
async def get_skill(skill_name: str, request: Request):
    """获取单个 Skill 详情。"""
    registry = request.app.state.skill_registry
    skill = registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")
    return {
        "name": skill.metadata.name,
        "version": skill.metadata.version,
        "description": skill.metadata.description,
        "skill_type": skill.metadata.skill_type,
        "trigger_words": skill.metadata.trigger_words,
        "inputs": [i.model_dump() for i in skill.metadata.inputs],
        "outputs": [o.model_dump() for o in skill.metadata.outputs],
        "execution": skill.metadata.execution,
        "enabled": skill.metadata.enabled,
        "timeout": skill.metadata.timeout,
        "sandbox": skill.metadata.sandbox,
        "description_md": skill.description_md,
        "assets": list(registry.get_assets(skill_name).keys()),
        "references": list(registry.load_references(skill_name).keys()),
    }


@router.post("")
async def create_skill(req: SkillCreateRequest, request: Request):
    """创建新 Skill。"""
    from src.skills.skill_models import SkillMetadata

    registry = request.app.state.skill_registry
    executor = request.app.state.skill_executor
    agent = request.app.state.agent

    if registry.get_skill(req.name):
        raise HTTPException(400, f"Skill '{req.name}' 已存在")

    metadata = SkillMetadata(
        name=req.name, version=req.version, description=req.description,
        skill_type=req.skill_type, trigger_words=req.trigger_words,
        inputs=req.inputs, outputs=req.outputs, execution=req.execution,
        enabled=req.enabled,
    )

    warnings = registry.validate_skill(metadata)
    if warnings:
        raise HTTPException(400, f"校验失败: {'; '.join(warnings)}")

    try:
        skill = registry.create_skill(metadata, f"# {req.name}\n\n{req.description}\n")
    except ValueError as e:
        raise HTTPException(400, str(e))

    # 动态注册为 Agent Tool
    if metadata.enabled:
        from src.skills.skill_tool_adapter import skill_to_langchain_tool
        try:
            agent.register_tool(skill_to_langchain_tool(skill, executor))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("动态注册 Tool 失败: %s", e)

    return {"success": True, "name": skill.metadata.name}


@router.put("/{skill_name}")
async def update_skill(skill_name: str, req: SkillUpdateRequest, request: Request):
    """更新已有 Skill。"""
    registry = request.app.state.skill_registry
    agent = request.app.state.agent
    executor = request.app.state.skill_executor

    if not registry.get_skill(skill_name):
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")

    updates = {}
    for field in ["description", "version", "trigger_words", "execution", "enabled", "inputs", "outputs"]:
        val = getattr(req, field, None)
        if val is not None:
            if hasattr(val, "model_dump"):
                updates[field] = [v.model_dump() for v in val]
            else:
                updates[field] = val

    try:
        skill = registry.update_skill(skill_name, updates)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if skill and skill.metadata.enabled:
        from src.skills.skill_tool_adapter import skill_to_langchain_tool
        agent._tools = [t for t in agent._tools if t.name != f"skill_{skill_name}"]
        try:
            agent.register_tool(skill_to_langchain_tool(skill, executor))
            agent._llm_with_tools = None
        except Exception:
            pass

    return {"success": True, "name": skill_name}


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str, request: Request):
    """删除 Skill。"""
    registry = request.app.state.skill_registry
    agent = request.app.state.agent

    if not registry.get_skill(skill_name):
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")

    registry.delete_skill(skill_name)
    agent._tools = [t for t in agent._tools if t.name != f"skill_{skill_name}"]
    agent._llm_with_tools = None

    return {"success": True}


@router.post("/{skill_name}/execute")
async def execute_skill(skill_name: str, req: SkillExecuteRequest, request: Request):
    """执行指定 Skill。"""
    executor = request.app.state.skill_executor
    return await executor.execute(skill_name, req.args)


@router.get("/{skill_name}/references")
async def get_skill_references(skill_name: str, request: Request):
    """渐进式加载 Skill 的 references 目录。"""
    registry = request.app.state.skill_registry
    if not registry.get_skill(skill_name):
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")
    refs = registry.load_references(skill_name)
    return {"skill": skill_name, "files": list(refs.keys()), "total": len(refs)}


@router.post("/reload")
async def reload_skills(request: Request):
    """重新加载所有 Skill（从磁盘）。"""
    registry = request.app.state.skill_registry
    executor = request.app.state.skill_executor
    agent = request.app.state.agent

    agent._tools = [t for t in agent._tools if not t.name.startswith("skill_")]
    agent._llm_with_tools = None

    skills = registry.reload_all()

    from src.skills.skill_tool_adapter import register_skills_with_agent
    register_skills_with_agent(agent, registry, executor)

    return {"success": True, "count": len(skills)}


# ==================================================================
# ZIP 导入 / 导出
# ==================================================================

@router.post("/import")
async def import_skill_zip(file: UploadFile = File(...), request: Request = Request):
    """上传 ZIP 压缩包导入 Skill。ZIP 根目录必须包含 SKILL.md。"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "请上传 .zip 文件")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 50MB")

    # 解析 ZIP
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(400, "无效的 ZIP 文件")

    # 查找 SKILL.md — 可能在根目录或一级子目录下
    names = zf.namelist()
    skill_md_name = None
    prefix = ""
    for n in names:
        bn = os.path.basename(n)
        if bn == "SKILL.md" and not n.startswith("__MACOSX"):
            skill_md_name = n
            prefix = n.replace("SKILL.md", "")
            break

    if skill_md_name is None:
        raise HTTPException(400, "ZIP 中未找到 SKILL.md")

    # 读取并解析 SKILL.md frontmatter
    skill_md_content = zf.read(skill_md_name).decode("utf-8")
    from src.skills.skill_registry import SkillRegistry
    fm, body = SkillRegistry._parse_frontmatter(skill_md_content)

    if not fm or "name" not in fm:
        raise HTTPException(400, "SKILL.md frontmatter 缺少 name 字段")

    # 兼容第三方 SKILL.md：从 body 提取 description，填充默认值
    if not fm.get("description"):
        # 取 body 第一行非空非标题文本作为 description
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                fm["description"] = stripped[:200]
                break
        if not fm.get("description"):
            fm["description"] = fm["name"]

    # 设置默认 skill_type 和 execution（允许第三方 SKILL.md 缺少这些字段）
    fm.setdefault("skill_type", "http")
    fm.setdefault("execution", {})
    fm.setdefault("enabled", True)

    from src.skills.skill_models import SkillMetadata
    try:
        metadata = SkillMetadata(**fm)
    except Exception as e:
        raise HTTPException(400, f"元数据验证失败: {e}")

    # 检查重名
    registry = request.app.state.skill_registry
    if registry.get_skill(metadata.name):
        raise HTTPException(400, f"Skill '{metadata.name}' 已存在，请先删除或改名")

    # 写入磁盘
    skill_dir = Path(registry._root) / metadata.name
    skill_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["assets", "scripts", "references"]:
        (skill_dir / sub).mkdir(exist_ok=True)

    # 解压所有文件（排除 __MACOSX、.DS_Store 等）
    for name in names:
        if name.startswith("__MACOSX") or name.endswith(".DS_Store"):
            continue
        # 去掉前缀（一级子目录名）
        rel = name[len(prefix):]
        if not rel or rel.endswith("/"):
            continue
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(name))

    zf.close()

    # 注册到内存
    from src.skills.skill_tool_adapter import skill_to_langchain_tool
    skill = registry._load_skill_metadata(skill_dir)
    if skill is None:
        raise HTTPException(400, "SKILL.md 解析失败")
    registry._skills[metadata.name] = skill
    registry._preload_assets(skill_dir, metadata.name)

    # 注册为 Agent Tool
    executor = request.app.state.skill_executor
    agent = request.app.state.agent
    if metadata.enabled:
        try:
            agent.register_tool(skill_to_langchain_tool(skill, executor))
        except Exception:
            pass

    return {"success": True, "name": metadata.name, "type": metadata.skill_type,
            "description": metadata.description}


@router.get("/{skill_name}/export")
async def export_skill_zip(skill_name: str, request: Request):
    """导出 Skill 为 ZIP 压缩包下载。"""
    registry = request.app.state.skill_registry
    skill = registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")

    skill_dir = Path(skill.skill_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in skill_dir.rglob("*"):
            if fpath.is_file() and not fpath.name.startswith((".", "__")):
                arcname = f"{skill_name}/{fpath.relative_to(skill_dir)}"
                zf.write(fpath, arcname)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={skill_name}.zip"},
    )


# ==================================================================
# 文件浏览 / 编辑
# ==================================================================

@router.get("/{skill_name}/files")
async def list_skill_files(skill_name: str, request: Request):
    """列出 Skill 目录下所有文件（树形结构）。"""
    registry = request.app.state.skill_registry
    skill = registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")

    skill_dir = Path(skill.skill_dir)
    files = []
    for fpath in sorted(skill_dir.rglob("*")):
        if fpath.is_file() and not fpath.name.startswith((".", "__")):
            rel = str(fpath.relative_to(skill_dir))
            size = fpath.stat().st_size
            files.append({"path": rel, "name": fpath.name, "size": size})
    return {"skill": skill_name, "files": files, "total": len(files)}


@router.get("/{skill_name}/files/{file_path:path}")
async def read_skill_file(skill_name: str, file_path: str, request: Request):
    """读取 Skill 内指定文件内容。"""
    registry = request.app.state.skill_registry
    skill = registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")

    target = Path(skill.skill_dir) / file_path
    # 安全检查：不能跳出 skill 目录
    try:
        target.resolve().relative_to(Path(skill.skill_dir).resolve())
    except ValueError:
        raise HTTPException(403, "路径不合法")

    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"文件不存在: {file_path}")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"path": file_path, "content": None, "binary": True, "size": target.stat().st_size}

    return {"path": file_path, "content": content, "binary": False, "size": target.stat().st_size}


@router.put("/{skill_name}/files/{file_path:path}")
async def write_skill_file(skill_name: str, file_path: str, request: Request):
    """编辑/更新 Skill 内指定文件内容。"""
    registry = request.app.state.skill_registry
    skill = registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' 不存在")

    body = await request.json()
    content = body.get("content", "")

    target = Path(skill.skill_dir) / file_path
    try:
        target.resolve().relative_to(Path(skill.skill_dir).resolve())
    except ValueError:
        raise HTTPException(403, "路径不合法")

    # 确保父目录存在
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    # 如果编辑的是 SKILL.md，需要重新加载元数据
    if file_path == "SKILL.md":
        reloaded = registry._load_skill_metadata(Path(skill.skill_dir))
        if reloaded:
            registry._skills[skill_name] = reloaded
            registry.invalidate_references_cache(skill_name)
            # 重新注册 Tool
            executor = request.app.state.skill_executor
            agent = request.app.state.agent
            if reloaded.metadata.enabled:
                from src.skills.skill_tool_adapter import skill_to_langchain_tool
                agent._tools = [t for t in agent._tools if t.name != f"skill_{skill_name}"]
                try:
                    agent.register_tool(skill_to_langchain_tool(reloaded, executor))
                    agent._llm_with_tools = None
                except Exception:
                    pass

    return {"success": True, "path": file_path}
