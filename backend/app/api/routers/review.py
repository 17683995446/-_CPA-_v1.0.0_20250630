"""
FSRS 间隔重复复习路由。

业务规范：
- 每日到期卡片需复习
- 复习评分 1-4 对应 Again/Hard/Good/Easy
- FSRS 引擎根据评分更新卡片调度状态
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_fsrs_engine
from app.db.session import get_db
from app.engines.fsrs import Card, FSRSEngine, Rating
from app.models import ReviewCard, ReviewLog
from app.schemas.review import (
    DueCardsResponse,
    ReviewCardResponse,
    SubmitReviewRequest,
    SubmitReviewResponse,
)

router = APIRouter(prefix="/api/review", tags=["间隔重复"])


@router.get("/{user_id}/due", response_model=DueCardsResponse)
def get_due_cards(
    user_id: int,
    target_date: date | None = None,
    db: Session = Depends(get_db),
):
    """获取用户今日到期卡片。"""
    target = target_date or date.today()
    cards = (
        db.query(ReviewCard)
        .filter(ReviewCard.user_id == user_id, ReviewCard.due <= target)
        .all()
    )
    return DueCardsResponse(
        total=len(cards),
        cards=[
            ReviewCardResponse(
                id=c.id,
                question_id=c.question_id,
                knowledge_point_id=c.knowledge_point_id,
                stability=c.stability,
                difficulty=c.difficulty,
                due=c.due,
                last_review=c.last_review.isoformat() if c.last_review else None,
                reps=c.reps,
                lapses=c.lapses,
                state=c.state,
            )
            for c in cards
        ],
    )


@router.post("/{user_id}/cards/{card_id}", response_model=SubmitReviewResponse)
def submit_review(
    user_id: int,
    card_id: int,
    req: SubmitReviewRequest,
    db: Session = Depends(get_db),
    fsrs_engine: FSRSEngine = Depends(get_fsrs_engine),
):
    """提交复习评分，更新卡片调度状态。"""
    card_orm = (
        db.query(ReviewCard)
        .filter(ReviewCard.id == card_id, ReviewCard.user_id == user_id)
        .first()
    )
    if card_orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"复习卡片 {card_id} 不存在",
        )

    card = Card.from_orm(card_orm)
    rating = Rating(req.rating)
    now = datetime.now()

    result = fsrs_engine.review(card, rating, now)

    # 写回 ORM
    card.to_orm(card_orm)

    # 记录复习日志
    log = ReviewLog(
        card_id=card_orm.id,
        user_id=user_id,
        rating=req.rating,
        review_time=now,
        elapsed_days=result.elapsed_days,
        scheduled_days=result.interval,
        state=card_orm.state,
        stability_before=result.stability_before,
        difficulty_before=result.difficulty_before,
        stability_after=result.stability_after,
        difficulty_after=result.difficulty_after,
    )
    db.add(log)
    db.commit()
    db.refresh(card_orm)

    return SubmitReviewResponse(
        card_id=card_orm.id,
        interval=result.interval,
        elapsed_days=result.elapsed_days,
        retrievability=result.retrievability,
        stability_before=result.stability_before,
        stability_after=result.stability_after,
        difficulty_before=result.difficulty_before,
        difficulty_after=result.difficulty_after,
        next_due=card_orm.due,
        state=card_orm.state,
    )


@router.post("/{user_id}/cards", response_model=ReviewCardResponse, status_code=status.HTTP_201_CREATED)
def create_review_card(
    user_id: int,
    question_id: int,
    knowledge_point_id: int,
    db: Session = Depends(get_db),
):
    """为用户创建复习卡片（关联题目和知识点）。"""
    card = ReviewCard(
        user_id=user_id,
        question_id=question_id,
        knowledge_point_id=knowledge_point_id,
        due=date.today(),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
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
