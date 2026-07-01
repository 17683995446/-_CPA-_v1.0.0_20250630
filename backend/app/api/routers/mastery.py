"""
BKT 知识追踪路由（集成 BKT + FSRS + 游戏化）。

第一性原理：一次答题应同时驱动三个引擎：
1. BKT 更新知识掌握度（p_known）
2. FSRS 更新复习卡片调度（如有卡片）
3. 游戏化计算 XP 奖励、检查等级和成就

这是 CPA 学习系统的核心循环，所有引擎在此交汇。
业务编排逻辑已抽离至 AnswerService，路由层保持薄。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    get_bkt_engine,
    get_fsrs_engine,
    get_gamification_engine,
    get_user_or_404,
)
from app.db.session import get_db
from app.engines.bkt import BKTEngine, MasteryState
from app.engines.fsrs import FSRSEngine
from app.engines.gamification import GamificationEngine
from app.models import KnowledgePoint, User, UserMastery
from app.schemas.mastery import (
    BatchMasteryResponse,
    MasteryItemResponse,
    MasteryResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services import AnswerService

router = APIRouter(prefix="/api/mastery", tags=["知识追踪"])


def _get_answer_service(
    bkt_engine: BKTEngine = Depends(get_bkt_engine),
    fsrs_engine: FSRSEngine = Depends(get_fsrs_engine),
    game_engine: GamificationEngine = Depends(get_gamification_engine),
) -> AnswerService:
    """构造 AnswerService 实例。"""
    return AnswerService(bkt_engine, fsrs_engine, game_engine)


@router.get("/{user_id}/all", response_model=BatchMasteryResponse)
def get_all_mastery(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_or_404),
    bkt_engine: BKTEngine = Depends(get_bkt_engine),
):
    """
    批量获取用户所有知识点的掌握度。

    一次请求返回全部知识点的 BKT 掌握度，避免前端 N+1 调用。
    未答题的知识点返回 BKT 默认值（p_known=0.1, level=unknown）。
    供知识可视化模块渲染掌握度热力图。
    """
    all_kps = db.query(KnowledgePoint).all()
    mastery_map = {
        m.knowledge_point_id: m
        for m in db.query(UserMastery).filter(UserMastery.user_id == user_id).all()
    }

    items: list[MasteryItemResponse] = []
    answered_count = 0
    for kp in all_kps:
        mastery = mastery_map.get(kp.id)
        if mastery is not None:
            state = MasteryState.from_orm(mastery)
            items.append(
                MasteryItemResponse(
                    knowledge_point_id=kp.id,
                    knowledge_point_code=kp.code,
                    knowledge_point_name=kp.name,
                    subject=kp.subject,
                    chapter=kp.chapter,
                    difficulty=kp.difficulty,
                    p_known=state.p_known,
                    mastery_level=bkt_engine.mastery_level(state),
                    total_answers=mastery.total_answers,
                    correct_answers=mastery.correct_answers,
                    recommended_difficulty=bkt_engine.recommend_difficulty(state),
                )
            )
            answered_count += 1
        else:
            default_state = MasteryState(
                p_known=bkt_engine.defaults.p_known,
                p_transit=bkt_engine.defaults.p_transit,
                p_guess=bkt_engine.defaults.p_guess,
                p_slip=bkt_engine.defaults.p_slip,
            )
            items.append(
                MasteryItemResponse(
                    knowledge_point_id=kp.id,
                    knowledge_point_code=kp.code,
                    knowledge_point_name=kp.name,
                    subject=kp.subject,
                    chapter=kp.chapter,
                    difficulty=kp.difficulty,
                    p_known=default_state.p_known,
                    mastery_level=bkt_engine.mastery_level(default_state),
                    total_answers=0,
                    correct_answers=0,
                    recommended_difficulty=bkt_engine.recommend_difficulty(default_state),
                )
            )

    return BatchMasteryResponse(
        user_id=user_id,
        total_kps=len(items),
        answered_kps=answered_count,
        items=items,
    )


@router.get("/{user_id}/{kp_id}", response_model=MasteryResponse)
def get_mastery(
    user_id: int,
    kp_id: int,
    db: Session = Depends(get_db),
    bkt_engine: BKTEngine = Depends(get_bkt_engine),
):
    """获取用户对某知识点的掌握度。"""
    mastery_orm = AnswerService._get_or_create_mastery(db, user_id, kp_id, bkt_engine)
    state = MasteryState.from_orm(mastery_orm)
    return MasteryResponse(
        knowledge_point_id=kp_id,
        p_known=state.p_known,
        p_transit=state.p_transit,
        p_guess=state.p_guess,
        p_slip=state.p_slip,
        total_answers=mastery_orm.total_answers,
        correct_answers=mastery_orm.correct_answers,
        mastery_level=bkt_engine.mastery_level(state),
        recommended_difficulty=bkt_engine.recommend_difficulty(state),
    )


@router.post("/{user_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(
    user_id: int,
    req: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_or_404),
    answer_service: AnswerService = Depends(_get_answer_service),
):
    """
    提交答题结果（核心循环）。

    一次答题同时驱动 BKT + FSRS + 游戏化三个引擎。
    业务逻辑委托给 AnswerService，路由层仅负责参数解析和响应构造。
    """
    result = answer_service.submit(
        db=db,
        user=user,
        knowledge_point_id=req.knowledge_point_id,
        is_correct=req.is_correct,
        difficulty=req.difficulty,
        question_id=req.question_id,
        rating=req.rating,
        seed=req.seed,
    )

    return SubmitAnswerResponse(
        p_known_before=result.p_known_before,
        p_known_after=result.p_known_after,
        mastery_level=result.mastery_level,
        recommended_difficulty=result.recommended_difficulty,
        fsrs_updated=result.fsrs_updated,
        next_due=result.next_due,
        interval=result.interval,
        stability_after=result.stability_after,
        xp_earned=result.xp_earned,
        xp_reason=result.xp_reason,
        is_critical=result.is_critical,
        total_xp=result.total_xp,
        current_level=result.current_level,
        level_up=result.level_up,
        should_celebrate=result.should_celebrate,
    )
