"""
通用 Schema：统一响应包装。

架构规范：
- 所有 API 响应使用统一格式 {code, message, data}
- 便于前端统一处理错误和成功响应
"""
from typing import Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel):
    """统一 API 响应格式。"""

    code: int = 200
    message: str = "success"
    data: Optional[dict] = None


class MessageResponse(BaseModel):
    """简单消息响应。"""

    message: str
