"""
HTTP 中间件模块。

架构规范：
- 安全头中间件为所有响应注入标准 HTTP 安全头
- CORS 中间件处理跨域请求（如开发环境前后端分离）
- 中间件不包含业务逻辑，仅关注 HTTP 层面
"""
from fastapi import FastAPI, Request


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


def register_middleware(app: FastAPI) -> None:
    """注册所有中间件到 FastAPI 应用实例。

    使用集中注册而非分散的 @app.middleware 装饰器，
    便于维护和测试。
    """

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """为所有响应注入安全相关的 HTTP 头。"""
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        response.headers["Content-Security-Policy"] = CSP_POLICY
        return response
