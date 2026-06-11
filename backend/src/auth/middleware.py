"""认证网关中间件 — FastAPI Middleware 统一拦截 /api/* 请求。

流程:
1. 白名单路径直接放行
2. WebSocket 通过 query param ?token=xxx 认证
3. 普通 HTTP 从 Authorization header 提取 Bearer token
4. 无 token 或 token 无效 → 返回 401
5. token 有效 → 将 user_id/username/role 注入 request.state
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.auth.jwt_utils import decode_token

logger = logging.getLogger(__name__)

# 不需要认证的路径精确匹配
PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# 不需要认证的路径前缀（注意：不要把 /api/auth/ 放这里，
# 否则 /api/auth/me 等需要认证的路径也被放行）
PUBLIC_PREFIXES: list[str] = []


def _extract_token(request: Request) -> str | None:
    """从 header 或 query param 提取 token。"""
    # 1. Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # 2. Query param（用于 WebSocket）
    token = request.query_params.get("token")
    if token:
        return token

    return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. 白名单放行
        if path in PUBLIC_PATHS:
            return await call_next(request)
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)
        # 非 /api/ 路径放行（静态文件等）
        if not path.startswith("/api/"):
            return await call_next(request)

        # 2. 提取并验证 token
        token = _extract_token(request)
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "未提供认证令牌", "code": "TOKEN_MISSING"},
            )

        payload = decode_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "认证令牌无效或已过期", "code": "TOKEN_INVALID"},
            )

        # 3. 注入用户信息到 request.state
        request.state.user_id = int(payload["sub"])
        request.state.username = payload["username"]
        request.state.user_role = payload["role"]

        return await call_next(request)


def require_role(*roles: str):
    """角色检查装饰器/依赖 — 用于路由级别精细控制。"""
    from functools import wraps
    from fastapi import HTTPException, Request

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            # 从参数中找到 request
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if request is None:
                request = kwargs.get("request")

            if request and hasattr(request, "state"):
                user_role = getattr(request.state, "user_role", None)
                if user_role not in roles:
                    raise HTTPException(403, "权限不足")
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator
