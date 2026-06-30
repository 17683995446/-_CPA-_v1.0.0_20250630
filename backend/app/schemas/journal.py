"""
会计分录判错相关 Schema。

业务规范：
- 借贷记账法：有借必有贷，借贷必相等
- 科目方向：资产/费用借增贷减，负债/权益/收入贷增借减
- 验证引擎收集所有错误，一次性反馈
"""
from typing import Optional

from pydantic import BaseModel, Field


class JournalEntryLineRequest(BaseModel):
    """会计分录单行请求。"""

    account: str = Field(..., description="科目名称")
    direction: str = Field(..., description="方向：借 / 贷")
    amount: float = Field(..., description="金额")


class JournalValidationRequest(BaseModel):
    """分录验证请求。"""

    lines: list[JournalEntryLineRequest] = Field(..., description="分录行列表")


class ValidationErrorResponse(BaseModel):
    """验证错误响应。"""

    error_type: str
    message: str
    line_index: Optional[int] = None
    account: Optional[str] = None


class CorrectionSuggestionResponse(BaseModel):
    """修正建议响应。"""

    error_type: str
    suggestion: str


class JournalValidationResponse(BaseModel):
    """分录验证结果响应。"""

    is_valid: bool
    errors: list[ValidationErrorResponse] = Field(default_factory=list)
    total_debit: float = 0.0
    total_credit: float = 0.0
    balance_diff: float = 0.0
    corrections: list[CorrectionSuggestionResponse] = Field(default_factory=list)
    explanation: Optional[str] = None
