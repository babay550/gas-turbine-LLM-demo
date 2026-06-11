"""认证 API — 登录、获取当前用户、修改密码。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from src.auth.jwt_utils import create_token
from src.auth.password import verify_password, hash_password
from src.auth.models import User
from src.db.engine import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
async def login(data: LoginRequest):
    """用户登录，返回 JWT token。"""
    with get_session() as session:
        user = session.query(User).filter(
            User.username == data.username,
            User.is_active == True,
        ).first()

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(401, "用户名或密码错误")

        # 更新最后登录时间
        user.last_login = datetime.now()
        session.commit()

        token = create_token(user.id, user.username, user.role)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user.to_dict(include_org=True),
        }


@router.post("/register")
async def register(data: LoginRequest):
    """用户注册（可选，生产环境可关闭）。"""
    with get_session() as session:
        if session.query(User).filter(User.username == data.username).first():
            raise HTTPException(400, "用户名已存在")

        from src.auth.password import hash_password
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            display_name=data.username,
            role="viewer",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_token(user.id, user.username, user.role)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user.to_dict(),
        }


@router.get("/me")
async def get_current_user(request: Request):
    """获取当前登录用户信息。"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(401, "未认证")

    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")
        return user.to_dict(include_org=True)


@router.put("/me/password")
async def change_password(request: Request, data: ChangePasswordRequest):
    """修改当前用户密码。"""
    user_id = request.state.user_id
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")

        if not verify_password(data.old_password, user.password_hash):
            raise HTTPException(400, "原密码错误")

        user.password_hash = hash_password(data.new_password)
        user.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "密码修改成功"}
