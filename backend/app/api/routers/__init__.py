"""
路由包汇总。

架构规范：
- 每个路由文件对应一个业务域，前缀统一为 /api
- 路由层仅负责 HTTP 参数解析、权限校验和响应构造
- 业务逻辑委托给 Service 层或 Engine 层
- 使用 register_routes() 集中注册，避免 main.py 中逐一导入
"""
from fastapi import FastAPI
from fastapi.routing import APIRouter

from app.api.routers import (
    gamification,
    journal,
    knowledge,
    llm,
    mastery,
    questions,
    review,
    study,
    users,
)

# 路由模块及 OpenAPI 标签元数据（注册顺序即文档显示顺序）
_ROUTER_MODULES: list[tuple[APIRouter, str, str]] = [
    (users.router, "用户管理", "用户注册、查询、信息管理"),
    (knowledge.router, "知识图谱", "知识点、知识边、学习路径、可视化"),
    (questions.router, "题目管理", "按知识点出题、随机出题、变体生成"),
    (review.router, "复习系统", "FSRS 间隔重复复习卡片管理"),
    (mastery.router, "掌握度追踪", "BKT 知识追踪、批量掌握度查询"),
    (gamification.router, "游戏化", "等级、XP、成就、连续学习"),
    (journal.router, "学习日志", "会计分录判错练习"),
    (study.router, "学习会话", "学习会话管理、答题记录"),
    (llm.router, "智能分析", "LLM 错题归因、诊断报告、相似题推荐、解析增强"),
]


def register_routes(app: FastAPI) -> None:
    """将所有业务路由注册到 FastAPI 应用实例。

    使用集中注册替代 main.py 中的逐一 include_router 调用，
    新增路由只需在此列表中添加模块即可。
    每个路由模块携带 OpenAPI 标签元数据，使 API 文档自动分组。
    """
    for router, tag_name, tag_desc in _ROUTER_MODULES:
        # 确保 router 的 tags 包含中文标签
        if not router.tags:
            router.tags = [tag_name]
        app.include_router(router)


__all__ = ["register_routes"]
