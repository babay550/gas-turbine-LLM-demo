"""用户管理 API — CRUD、角色分配、密码重置（admin 权限）。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from src.auth.models import User, Organization
from src.auth.password import hash_password
from src.db.engine import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_admin(request: Request):
    """检查是否为 admin 角色。"""
    role = getattr(request.state, "user_role", None)
    if role != "admin":
        raise HTTPException(403, "需要管理员权限")


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    email: str = ""
    phone: str = ""
    role: str = "viewer"
    org_id: int | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    org_id: int | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class RoleUpdate(BaseModel):
    role: str


@router.get("")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    role: str = Query(None),
):
    """获取用户列表（admin）。"""
    _check_admin(request)
    with get_session() as session:
        query = session.query(User)
        if search:
            query = query.filter(
                (User.username.contains(search)) |
                (User.display_name.contains(search))
            )
        if role:
            query = query.filter(User.role == role)

        total = query.count()
        users = query.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "users": [u.to_dict(include_org=True) for u in users],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.post("")
async def create_user(request: Request, data: UserCreate):
    """创建用户（admin）。"""
    _check_admin(request)
    if data.role not in ("admin", "engineer", "viewer"):
        raise HTTPException(400, "无效的角色")

    with get_session() as session:
        if session.query(User).filter(User.username == data.username).first():
            raise HTTPException(400, "用户名已存在")

        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            display_name=data.display_name or data.username,
            email=data.email,
            phone=data.phone,
            role=data.role,
            org_id=data.org_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"success": True, "id": user.id, "message": "用户创建成功"}


@router.put("/{user_id}")
async def update_user(user_id: int, request: Request, data: UserUpdate):
    """修改用户信息（admin）。"""
    _check_admin(request)
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")
        update_data = data.model_dump(exclude_unset=True)
        if "role" in update_data and update_data["role"] not in ("admin", "engineer", "viewer"):
            raise HTTPException(400, "无效的角色")
        for k, v in update_data.items():
            setattr(user, k, v)
        user.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "用户信息已更新"}


@router.delete("/{user_id}")
async def delete_user(user_id: int, request: Request):
    """禁用用户（软删除，admin）。"""
    _check_admin(request)
    if user_id == request.state.user_id:
        raise HTTPException(400, "不能禁用自己")
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")
        if user.username == "admin":
            raise HTTPException(400, "不能禁用默认管理员")
        user.is_active = False
        user.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "用户已禁用"}


@router.put("/{user_id}/password")
async def reset_password(user_id: int, request: Request, data: ResetPasswordRequest):
    """重置用户密码（admin）。"""
    _check_admin(request)
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")
        user.password_hash = hash_password(data.new_password)
        user.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "密码已重置"}


@router.put("/{user_id}/role")
async def update_role(user_id: int, request: Request, data: RoleUpdate):
    """修改用户角色（admin）。"""
    _check_admin(request)
    if data.role not in ("admin", "engineer", "viewer"):
        raise HTTPException(400, "无效的角色")
    if user_id == request.state.user_id:
        raise HTTPException(400, "不能修改自己的角色")

    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")
        user.role = data.role
        user.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": f"角色已修改为 {data.role}"}
