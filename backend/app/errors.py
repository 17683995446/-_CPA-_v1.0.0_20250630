"""
错误码体系与异常定义。

架构规范：
- 业务错误使用 ErrorCode 枚举统一编码
- 自定义异常携带错误码，由全局处理器转为标准响应
- 错误码格式：{HTTP状态码}{业务编号}，如 40001 = 400 + 001

第一性原理：错误处理应可追溯、可分类、前端可统一处理。
"""
from enum import IntEnum

from fastapi import HTTPException


class ErrorCode(IntEnum):
    """业务错误码枚举。

    编码规则：前3位为 HTTP 状态码基码，后2位为业务序号。
    """

    # --- 通用错误 (400) ---
    INVALID_PARAMS = 40001
    RESOURCE_NOT_FOUND = 40401
    METHOD_NOT_ALLOWED = 40501

    # --- 用户相关 (400/409) ---
    USER_NOT_FOUND = 40402
    USER_ALREADY_EXISTS = 40901
    INVALID_PASSWORD = 40002

    # --- 题库相关 (400/404) ---
    QUESTION_NOT_FOUND = 40403
    INSUFFICIENT_QUESTIONS = 40003
    INVALID_QUESTION_TYPE = 40004

    # --- 知识点相关 (404) ---
    KP_NOT_FOUND = 40404

    # --- 复习系统相关 (400) ---
    NO_DUE_CARDS = 40005
    INVALID_RATING = 40006

    # --- 掌握度相关 (400) ---
    MASTERY_NOT_FOUND = 40405

    # --- 分录判错相关 (400) ---
    INVALID_JOURNAL_ENTRY = 40007

    # --- 服务器错误 (500) ---
    INTERNAL_ERROR = 50001
    DB_ERROR = 50002


class BusinessException(HTTPException):
    """业务异常基类，携带 ErrorCode。

    使用方式：
        raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户 123 不存在")
    """

    def __init__(
        self,
        error_code: ErrorCode,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.error_code = error_code
        super().__init__(
            status_code=error_code // 100,  # 前3位为 HTTP 状态码
            detail=detail or error_code.name,
            headers=headers,
        )


# 错误码到消息的默认映射
DEFAULT_ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_PARAMS: "请求参数无效",
    ErrorCode.RESOURCE_NOT_FOUND: "请求的资源不存在",
    ErrorCode.METHOD_NOT_ALLOWED: "不支持的请求方法",
    ErrorCode.USER_NOT_FOUND: "用户不存在",
    ErrorCode.USER_ALREADY_EXISTS: "用户已存在",
    ErrorCode.INVALID_PASSWORD: "密码无效",
    ErrorCode.QUESTION_NOT_FOUND: "题目不存在",
    ErrorCode.INSUFFICIENT_QUESTIONS: "题目数量不足",
    ErrorCode.INVALID_QUESTION_TYPE: "题目类型无效",
    ErrorCode.KP_NOT_FOUND: "知识点不存在",
    ErrorCode.NO_DUE_CARDS: "没有到期的复习卡片",
    ErrorCode.INVALID_RATING: "复习评分无效",
    ErrorCode.MASTERY_NOT_FOUND: "掌握度记录不存在",
    ErrorCode.INVALID_JOURNAL_ENTRY: "会计分录格式无效",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
    ErrorCode.DB_ERROR: "数据库操作失败",
}
