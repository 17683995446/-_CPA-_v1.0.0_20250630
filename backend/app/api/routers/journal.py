"""
会计分录判错路由。

业务规范：
- 借贷记账法：有借必有贷，借贷必相等
- 验证引擎收集所有错误，一次性反馈
- 提供修正建议和分录解释
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_journal_validator
from app.engines.journal_validator import (
    JournalEntryLine,
    JournalEntryValidator,
)
from app.schemas.journal import (
    CorrectionSuggestionResponse,
    JournalValidationRequest,
    JournalValidationResponse,
    ValidationErrorResponse,
)

router = APIRouter(prefix="/api/journal", tags=["分录判错"])


@router.post("/validate", response_model=JournalValidationResponse)
def validate_journal_entry(
    req: JournalValidationRequest,
    validator: JournalEntryValidator = Depends(get_journal_validator),
) -> JournalValidationResponse:
    """验证会计分录。"""
    lines = [
        JournalEntryLine(
            account=line.account,
            direction=line.direction,
            amount=line.amount,
        )
        for line in req.lines
    ]

    result = validator.validate(lines)

    # 生成修正建议
    corrections = []
    for error in result.errors:
        suggestion = validator.suggest_correction(lines, error)
        if suggestion:
            corrections.append(
                CorrectionSuggestionResponse(
                    error_type=error.error_type.value,
                    suggestion=suggestion,
                )
            )

    # 生成分录解释
    explanation = validator.explain_entry(lines) if lines else None

    return JournalValidationResponse(
        is_valid=result.is_valid,
        errors=[
            ValidationErrorResponse(
                error_type=e.error_type.value,
                message=e.message,
                line_index=e.line_index,
                account=e.account,
            )
            for e in result.errors
        ],
        total_debit=result.total_debit,
        total_credit=result.total_credit,
        balance_diff=result.balance_diff,
        corrections=corrections,
        explanation=explanation,
    )


@router.get("/accounts")
def list_standard_accounts(
    validator: JournalEntryValidator = Depends(get_journal_validator),
) -> dict:
    """列出标准会计科目表。"""
    return {
        account: account_type.value
        for account, account_type in validator.accounts.items()
    }
