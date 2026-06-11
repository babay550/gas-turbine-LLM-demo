"""Skill 注册中心 — 扫描磁盘、解析 SKILL.md frontmatter、渐进式加载 assets/references。"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import yaml

from src.skills.skill_models import SkillDefinition, SkillMetadata

logger = logging.getLogger(__name__)


class SkillRegistry:
    """管理 backend/skills/ 下所有 Skill 的生命周期。

    渐进式加载策略：
      - 启动时：只读 SKILL.md frontmatter + assets/（常驻内存）
      - 执行时：按需加载 references/（懒加载，首次访问时读取并缓存）
    """

    def __init__(self, skills_root: str):
        self._root = Path(skills_root)
        self._skills: dict[str, SkillDefinition] = {}
        self._assets_cache: dict[str, dict[str, str]] = {}       # name → {filename: content}
        self._references_cache: dict[str, dict[str, str]] = {}   # name → {filename: content}

    # ------------------------------------------------------------------
    # Frontmatter 解析（与 WikiManager 同模式）
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """从 SKILL.md 文本中解析 YAML frontmatter，返回 (frontmatter_dict, body)。"""
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
            # 第三方 SKILL.md 的 description 可能包含 ": " 导致 YAML ScannerError
            # fallback：逐行用正则提取简单 key: value
            fm = SkillRegistry._regex_parse_frontmatter(fm_text)
        return fm, body

    @staticmethod
    def _regex_parse_frontmatter(fm_text: str) -> dict:
        """YAML 解析失败的 fallback：用正则逐行提取顶层 key: value。
        支持的类型推导：list（含中括号或逗号分隔）、bool、int、float、str。
        """
        import re
        fm: dict = {}
        for line in fm_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 只匹配顶层 key: value（第一个 ": "）
            m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.+)$', line)
            if not m:
                continue
            key, raw_val = m.group(1), m.group(2).strip()

            # 类型推导
            if raw_val.startswith("[") and raw_val.endswith("]"):
                # YAML flow sequence: [a, b, c]
                fm[key] = [s.strip().strip('"').strip("'") for s in raw_val[1:-1].split(",") if s.strip()]
            elif raw_val.lower() in ("true", "yes"):
                fm[key] = True
            elif raw_val.lower() in ("false", "no"):
                fm[key] = False
            else:
                try:
                    fm[key] = int(raw_val)
                except ValueError:
                    try:
                        fm[key] = float(raw_val)
                    except ValueError:
                        # 去掉可选的引号
                        if (raw_val.startswith('"') and raw_val.endswith('"')) or \
                           (raw_val.startswith("'") and raw_val.endswith("'")):
                            fm[key] = raw_val[1:-1]
                        else:
                            fm[key] = raw_val
        return fm

    @staticmethod
    def _serialize_skill_md(frontmatter: dict, content: str) -> str:
        """将 frontmatter + content 序列化为 SKILL.md 格式。"""
        fm = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"---\n{fm}---\n\n{content}\n"

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_all(self) -> dict[str, SkillDefinition]:
        """扫描 skills_root，加载所有合法 Skill（frontmatter + assets）。"""
        self._skills.clear()
        self._assets_cache.clear()
        # references 不清空——可能还在使用中，下次访问会重新加载

        if not self._root.exists():
            self._root.mkdir(parents=True, exist_ok=True)
            logger.info("Skill 根目录已创建: %s", self._root)
            return self._skills

        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            skill = self._load_skill_metadata(entry)
            if skill is not None:
                self._skills[skill.metadata.name] = skill
                self._preload_assets(entry, skill.metadata.name)

        logger.info("已加载 %d 个 Skill: %s", len(self._skills), list(self._skills.keys()))
        return self._skills

    def _load_skill_metadata(self, skill_dir: Path) -> SkillDefinition | None:
        """从 SKILL.md 解析 frontmatter 生成 SkillDefinition。"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            logger.warning("跳过 %s: 缺少 SKILL.md", skill_dir.name)
            return None

        try:
            text = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("读取 %s 失败: %s", skill_md, e)
            return None

        fm, body = self._parse_frontmatter(text)
        if not fm or "name" not in fm:
            logger.warning("%s: frontmatter 缺少 name 字段", skill_dir.name)
            return None

        try:
            metadata = SkillMetadata(**fm)
        except Exception as e:
            logger.error("验证 %s 元数据失败: %s", skill_dir.name, e)
            return None

        return SkillDefinition(
            metadata=metadata,
            description_md=body,
            skill_dir=str(skill_dir),
        )

    # ------------------------------------------------------------------
    # 渐进式加载：assets（预加载）和 references（懒加载）
    # ------------------------------------------------------------------

    def _preload_assets(self, skill_dir: Path, skill_name: str):
        """启动时预加载 assets/ 目录下所有文件到内存。"""
        assets_dir = skill_dir / "assets"
        if not assets_dir.exists():
            return
        assets = {}
        for f in assets_dir.rglob("*"):
            if f.is_file() and not f.name.startswith((".", "_")):
                try:
                    rel = str(f.relative_to(assets_dir))
                    assets[rel] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass  # 二进制文件等跳过
        if assets:
            self._assets_cache[skill_name] = assets
            logger.debug("预加载 %s assets: %d 个文件", skill_name, len(assets))

    def get_assets(self, skill_name: str) -> dict[str, str]:
        """获取已缓存的 assets。"""
        return self._assets_cache.get(skill_name, {})

    def load_references(self, skill_name: str) -> dict[str, str]:
        """渐进式加载 references/（首次访问时读取并缓存）。"""
        if skill_name in self._references_cache:
            return self._references_cache[skill_name]

        skill = self._skills.get(skill_name)
        if skill is None:
            return {}

        ref_dir = Path(skill.skill_dir) / "references"
        if not ref_dir.exists():
            self._references_cache[skill_name] = {}
            return {}

        refs: dict[str, str] = {}
        for f in ref_dir.rglob("*"):
            if f.is_file() and not f.name.startswith((".", "_")):
                try:
                    rel = str(f.relative_to(ref_dir))
                    refs[rel] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        self._references_cache[skill_name] = refs
        logger.info("渐进加载 %s references: %d 个文件", skill_name, len(refs))
        return refs

    def invalidate_references_cache(self, skill_name: str):
        """清除指定 Skill 的 references 缓存（更新后调用）。"""
        self._references_cache.pop(skill_name, None)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_skill(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def list_skills(self, enabled_only: bool = False) -> list[SkillDefinition]:
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if s.metadata.enabled]
        return skills

    # ------------------------------------------------------------------
    # 验证
    # ------------------------------------------------------------------

    def validate_skill(self, metadata: SkillMetadata) -> list[str]:
        """验证 Skill 定义的合法性，返回警告列表。"""
        warnings: list[str] = []
        if not metadata.execution:
            warnings.append("缺少 execution 配置")
            return warnings

        dispatch = {
            "http": metadata.get_http_config,
            "dataset": metadata.get_dataset_config,
            "workflow": metadata.get_workflow_config,
            "python": metadata.get_python_config,
            "shell": metadata.get_shell_config,
            "db": metadata.get_db_config,
        }
        parser = dispatch.get(metadata.skill_type)
        if parser:
            try:
                parser()
            except Exception as e:
                warnings.append(f"execution 与 skill_type={metadata.skill_type} 不匹配: {e}")
        return warnings

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_skill(self, metadata: SkillMetadata, description_md: str = "") -> SkillDefinition:
        """在磁盘创建 Skill 目录及 SKILL.md，注册到内存。"""
        name = metadata.name
        skill_dir = self._root / name

        if skill_dir.exists():
            raise ValueError(f"Skill '{name}' 已存在")

        # 创建目录结构
        skill_dir.mkdir(parents=True)
        (skill_dir / "assets").mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()

        # 写入 SKILL.md（frontmatter + body）
        fm = metadata.model_dump(exclude_none=True)
        body = description_md or f"# {metadata.name}\n\n{metadata.description}\n"
        content = self._serialize_skill_md(fm, body)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        # 注册到内存 + 预加载 assets
        skill = SkillDefinition(metadata=metadata, description_md=body, skill_dir=str(skill_dir))
        self._skills[name] = skill
        self._preload_assets(skill_dir, name)

        logger.info("创建 Skill: %s (%s)", name, metadata.skill_type)
        return skill

    def update_skill(
        self,
        name: str,
        metadata_updates: dict | None = None,
        description_md: str | None = None,
    ) -> SkillDefinition | None:
        """更新已存在的 Skill（重写 SKILL.md）。"""
        skill = self._skills.get(name)
        if skill is None:
            return None

        skill_dir = Path(skill.skill_dir)

        # 合并元数据更新
        if metadata_updates:
            current = skill.metadata.model_dump()
            current.update(metadata_updates)
            new_meta = SkillMetadata(**current)
            skill.metadata = new_meta

        # 更新描述
        if description_md is not None:
            skill.description_md = description_md

        # 重写 SKILL.md
        fm = skill.metadata.model_dump(exclude_none=True)
        content = self._serialize_skill_md(fm, skill.description_md)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        # 清除 references 缓存
        self.invalidate_references_cache(name)

        logger.info("更新 Skill: %s", name)
        return skill

    def delete_skill(self, name: str) -> bool:
        """删除 Skill 目录及注册。"""
        skill = self._skills.get(name)
        if skill is None:
            return False

        skill_dir = Path(skill.skill_dir)
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        self._skills.pop(name, None)
        self._assets_cache.pop(name, None)
        self._references_cache.pop(name, None)

        logger.info("删除 Skill: %s", name)
        return True

    def reload_all(self) -> dict[str, SkillDefinition]:
        """重新加载所有 Skill。"""
        return self.load_all()
