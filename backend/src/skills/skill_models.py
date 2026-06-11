"""Skill 数据模型 — SKILL.md YAML frontmatter 结构定义。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


# ---- 输入输出字段 ----

class SkillInputField(BaseModel):
    name: str
    type: Literal["string", "number", "boolean", "object", "array"] = "string"
    description: str = ""
    required: bool = True
    default: Any = None


class SkillOutputField(BaseModel):
    name: str
    type: Literal["string", "number", "boolean", "object", "array"] = "string"
    description: str = ""


# ---- 执行配置（6 种 skill_type 对应不同 Schema）----

class HTTPConfig(BaseModel):
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    headers: dict[str, str] = {}
    query_params: dict[str, str] = {}
    body_template: str | None = None
    timeout: int = 30
    response_path: str | None = None


class DatasetConfig(BaseModel):
    source: Literal["wiki", "chunk_store"] = "chunk_store"
    query_template: str = "{{query}}"
    top_k: int = 10
    use_hybrid: bool = True


class WorkflowConfig(BaseModel):
    workflow_id: str
    pass_input_as: str = "user_input"


class PythonConfig(BaseModel):
    script: str = "scripts/main.py"
    interpreter: str = "python"
    env_vars: dict[str, str] = {}


class ShellConfig(BaseModel):
    script: str = "scripts/run.sh"
    interpreter: str = "bash"
    env_vars: dict[str, str] = {}


class DBConfig(BaseModel):
    connection_string: str
    query: str
    readonly: bool = True
    max_rows: int = 1000


# ---- Skill 类型 ----

SkillType = Literal["http", "dataset", "workflow", "python", "shell", "db"]


# ---- Skill 元数据（从 SKILL.md frontmatter 解析）----

class SkillMetadata(BaseModel):
    """SKILL.md YAML frontmatter 对应的完整元数据。"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    skill_type: SkillType = "http"
    trigger_words: list[str] = []
    inputs: list[SkillInputField] = []
    outputs: list[SkillOutputField] = []
    execution: dict[str, Any] = {}
    sandbox: bool = True
    timeout: int = 60
    enabled: bool = True

    def get_http_config(self) -> HTTPConfig:
        return HTTPConfig(**self.execution)

    def get_dataset_config(self) -> DatasetConfig:
        return DatasetConfig(**self.execution)

    def get_workflow_config(self) -> WorkflowConfig:
        return WorkflowConfig(**self.execution)

    def get_python_config(self) -> PythonConfig:
        return PythonConfig(**self.execution)

    def get_shell_config(self) -> ShellConfig:
        return ShellConfig(**self.execution)

    def get_db_config(self) -> DBConfig:
        return DBConfig(**self.execution)


# ---- Skill 完整定义 ----

class SkillDefinition(BaseModel):
    """完整 Skill = 元数据（frontmatter）+ 描述（Markdown body）+ 磁盘路径。"""
    metadata: SkillMetadata
    description_md: str = ""
    skill_dir: str = ""

    model_config = {"arbitrary_types_allowed": True}


# ---- API 请求模型 ----

class SkillCreateRequest(BaseModel):
    name: str
    description: str
    skill_type: SkillType
    version: str = "1.0.0"
    trigger_words: list[str] = []
    inputs: list[SkillInputField] = []
    outputs: list[SkillOutputField] = []
    execution: dict[str, Any] = {}
    enabled: bool = True


class SkillUpdateRequest(BaseModel):
    description: str | None = None
    version: str | None = None
    trigger_words: list[str] | None = None
    inputs: list[SkillInputField] | None = None
    outputs: list[SkillOutputField] | None = None
    execution: dict[str, Any] | None = None
    enabled: bool | None = None


class SkillExecuteRequest(BaseModel):
    args: dict[str, Any] = {}
