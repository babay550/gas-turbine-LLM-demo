"""JWT 工具 — Token 生成与验证。"""

import jwt
from datetime import datetime, timedelta, timezone

from src.config import get_settings


def create_token(user_id: int, username: str, role: str) -> str:
    """生成 JWT access token。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """解码并验证 JWT token。返回 payload 或 None。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
