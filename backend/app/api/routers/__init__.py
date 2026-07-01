"""
路由包汇总。

架构规范：
- 每个路由文件对应一个业务域，前缀统一为 /api
- 路由层仅负责 HTTP 参数解析、权限校验和响应构造
- 业务逻辑委托给 Service 层或 Engine 层
- 使用 register_routes() 集中注册，避免 main.py 中逐一导入
"""
from fastapi import FastAPI

from app.api.routers import (
    gamification,
    journal,
    knowledge,
    mastery,
    questions,
    review,
    study,
    users,
)

# 路由模块列表（注册顺序即 OpenAPI 文档中的显示顺序）
_ROUTER_MODULES = [
    users,
    knowledge,
    questions,
    review,
    mastery,
    gamification,
    journal,
    study,
]


def register_routes(app: FastAPI) -> None:
    """将所有业务路由注册到 FastAPI 应用实例。

    使用集中注册替代 main.py 中的逐一 include_router 调用，
    新增路由只需在此列表中添加模块即可。
    """
    for module in _ROUTER_MODULES:
        app.include_router(module.router)


__all__ = ["register_routes"]
