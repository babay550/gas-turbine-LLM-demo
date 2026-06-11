"""组织管理 API — 树形组织结构 CRUD（admin 权限）。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from src.auth.models import Organization
from src.db.engine import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_admin(request: Request):
    role = getattr(request.state, "user_role", None)
    if role != "admin":
        raise HTTPException(403, "需要管理员权限")


class OrgCreate(BaseModel):
    name: str
    parent_id: int | None = None
    code: str = ""
    description: str = ""
    sort_order: int = 0


class OrgUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    code: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


@router.get("")
async def list_organizations(request: Request):
    """获取组织树形结构。"""
    _check_admin(request)
    with get_session() as session:
        # 获取所有顶级组织（parent_id 为空）
        roots = session.query(Organization).filter(
            Organization.parent_id == None,
            Organization.is_active == True,
        ).order_by(Organization.sort_order).all()

        tree = [org.to_tree_dict() for org in roots]
        return {"organizations": tree}


@router.get("/flat")
async def list_organizations_flat(request: Request):
    """获取组织平铺列表（用于下拉选择）。"""
    with get_session() as session:
        orgs = session.query(Organization).filter(
            Organization.is_active == True,
        ).order_by(Organization.sort_order).all()
        return {"organizations": [o.to_dict() for o in orgs]}


@router.post("")
async def create_organization(request: Request, data: OrgCreate):
    """创建组织/部门（admin）。"""
    _check_admin(request)
    with get_session() as session:
        org = Organization(
            name=data.name,
            parent_id=data.parent_id,
            code=data.code or None,
            description=data.description,
            sort_order=data.sort_order,
        )
        session.add(org)
        session.commit()
        session.refresh(org)
        return {"success": True, "id": org.id, "message": f"组织 '{data.name}' 创建成功"}


@router.put("/{org_id}")
async def update_organization(org_id: int, request: Request, data: OrgUpdate):
    """修改组织（admin）。"""
    _check_admin(request)
    with get_session() as session:
        org = session.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(404, "组织不存在")
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(org, k, v)
        org.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "组织信息已更新"}


@router.delete("/{org_id}")
async def delete_organization(org_id: int, request: Request):
    """删除组织（admin，不能删除有子组织或有用户的）。"""
    _check_admin(request)
    with get_session() as session:
        org = session.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(404, "组织不存在")

        # 检查是否有子组织
        children = session.query(Organization).filter(
            Organization.parent_id == org_id,
            Organization.is_active == True,
        ).count()
        if children > 0:
            raise HTTPException(400, "该组织下有子组织，不能删除")

        # 检查是否有用户
        from src.auth.models import User
        user_count = session.query(User).filter(User.org_id == org_id).count()
        if user_count > 0:
            raise HTTPException(400, "该组织下有用户，不能删除")

        org.is_active = False
        org.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "组织已删除"}
