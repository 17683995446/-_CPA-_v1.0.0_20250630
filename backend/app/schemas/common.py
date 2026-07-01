"""
通用 Schema：统一响应包装与辅助工具。

架构规范：
- 所有 API 响应使用统一格式 {code, message, data}
- 便于前端统一处理错误和成功响应
- success() / error() 工厂函数确保格式一致
"""
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel):
    """统一 API 响应格式。"""

    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class MessageResponse(BaseModel):
    """简单消息响应。"""

    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    """分页列表响应。"""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size


# ===== 响应工厂函数 =====

def success(data: Any = None, message: str = "success") -> dict:
    """构造成功响应字典。

    使用方式：
        return success({"items": [...]})
        return success(message="操作完成")
    """
    return {"code": 200, "message": message, "data": data}


def error(message: str, code: int = 400, data: Any = None) -> dict:
    """构造错误响应字典。

    使用方式：
        return error("参数无效", code=422)
    """
    return {"code": code, "message": message, "data": data}


def not_found(message: str = "资源不存在") -> dict:
    """构造 404 响应。"""
    return {"code": 404, "message": message, "data": None}
