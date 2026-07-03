"""
HTTP 中间件模块。

架构规范：
- 安全头中间件为所有响应注入标准 HTTP 安全头
- 请求追踪中间件为每个请求生成唯一 ID，便于日志关联和问题排查
- CORS 中间件处理跨域请求（如开发环境前后端分离）
- 中间件不包含业务逻辑，仅关注 HTTP 层面
"""
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


# ===== 安全头常量 =====

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

CSP_POLICY: str = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件。

    为每个请求生成或透传唯一请求 ID：
    - 优先使用客户端传入的 X-Request-ID
    - 无则生成 UUID4
    - 注入到 request.state.request_id 供日志使用
    - 在响应头中返回 X-Request-ID
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def register_middleware(app: FastAPI) -> None:
    """注册所有中间件到 FastAPI 应用实例。

    注册顺序（从外到内）：
    1. 安全头 — 最外层，确保所有响应都带安全头
    2. 请求追踪 — 在安全头之后，业务逻辑之前
    """

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """为所有响应注入安全相关的 HTTP 头。"""
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        response.headers["Content-Security-Policy"] = CSP_POLICY
        return response

    app.add_middleware(RequestIdMiddleware)
