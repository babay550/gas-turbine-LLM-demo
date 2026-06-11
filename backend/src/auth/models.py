"""认证 ORM 模型 — 用户表 + 组织表。"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from src.db.models import Base  # 复用同一个 Base，确保所有表在同一个 metadata


class Organization(Base):
    """组织/部门表 — 支持树形结构。"""
    __tablename__ = "auth_organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("auth_organizations.id"), nullable=True)
    code = Column(String, unique=True)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    children = relationship("Organization", backref="parent", remote_side=[id], lazy="select")
    users = relationship("User", backref="organization", lazy="select")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "code": self.code or "",
            "description": self.description or "",
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_tree_dict(self):
        """返回树形结构节点。"""
        d = self.to_dict()
        d["children"] = [c.to_tree_dict() for c in (self.children or []) if c.is_active]
        return d


class User(Base):
    """用户表。"""
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    display_name = Column(String)
    email = Column(String)
    phone = Column(String)
    role = Column(String, nullable=False, default="viewer")  # admin / engineer / viewer
    org_id = Column(Integer, ForeignKey("auth_organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_role", "role"),
    )

    def to_dict(self, include_org=False):
        d = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or "",
            "email": self.email or "",
            "phone": self.phone or "",
            "role": self.role,
            "org_id": self.org_id,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_org and self.organization:
            d["org_name"] = self.organization.name
        return d
