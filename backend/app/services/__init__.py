"""
服务层模块。

架构规范：
- Service 层封装跨引擎的业务编排逻辑，将复杂流程从路由中抽离
- 路由层仅负责 HTTP 参数解析和响应构造，业务逻辑委托给 Service
- Service 不直接依赖 FastAPI，可独立单元测试
"""
from app.services.answer_service import AnswerService

__all__ = ["AnswerService"]
