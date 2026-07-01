"""
FSRS 间隔重复复习相关 Schema。

业务规范：
- 用户每日有到期卡片需要复习
- 复习评分 1-4 对应 Again/Hard/Good/Easy
- 复习后 FSRS 引擎更新卡片调度状态
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ReviewCardResponse(BaseModel):
    """复习卡片响应。"""

    id: int
    question_id: int
    knowledge_point_id: int
    stability: float
    difficulty: float
    due: date
    last_review: Optional[str] = None
    reps: int
    lapses: int
    state: str


class DueCardsResponse(BaseModel):
    """到期卡片列表响应。"""

    total: int
    cards: list[ReviewCardResponse]


class SubmitReviewRequest(BaseModel):
    """提交复习评分请求。"""

    rating: int = Field(..., ge=1, le=4, description="评分 1=Again 2=Hard 3=Good 4=Easy")


class SubmitReviewResponse(BaseModel):
    """复习结果响应。"""

    card_id: int
    interval: int
    elapsed_days: float
    retrievability: float
    stability_before: float
    stability_after: float
    difficulty_before: float
    difficulty_after: float
    next_due: date
    state: str


def review_card_to_response(card: "ReviewCard") -> ReviewCardResponse:
    """
    将 ReviewCard ORM 模型转换为 ReviewCardResponse。

    消除路由层重复的 ReviewCardResponse 构造逻辑（到期列表与创建卡片两处）。
    last_review 由 datetime 序列化为 ISO 格式字符串，其余字段直接映射。
    """
    return ReviewCardResponse(
        id=card.id,
        question_id=card.question_id,
        knowledge_point_id=card.knowledge_point_id,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due,
        last_review=card.last_review.isoformat() if card.last_review else None,
        reps=card.reps,
        lapses=card.lapses,
        state=card.state,
    )
