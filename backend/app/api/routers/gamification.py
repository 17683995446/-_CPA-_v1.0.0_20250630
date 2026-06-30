"""
游戏化激励路由。

业务规范：
- Streak：连续学习天数管理，支持保护卡
- XP/等级：经验值累计与等级计算
- 成就：条件触发式解锁
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_gamification_engine
from app.db.session import get_db
from app.engines.gamification import GamificationEngine, StreakInfo
from app.models import Achievement, User, UserAchievement, UserProfile, UserStreak
from app.schemas.gamification import (
    AchievementResponse,
    LevelInfoResponse,
    StreakResponse,
    StreakUpdateResponse,
    UpdateStreakRequest,
)

router = APIRouter(prefix="/api/gamification", tags=["游戏化"])


def _get_or_create_streak(db: Session, user_id: int) -> UserStreak:
    """获取或创建用户 streak 记录。"""
    streak_orm = db.query(UserStreak).filter(UserStreak.user_id == user_id).first()
    if streak_orm is None:
        streak_orm = UserStreak(user_id=user_id)
        db.add(streak_orm)
        db.flush()
    return streak_orm


@router.get("/{user_id}/streak", response_model=StreakResponse)
def get_streak(user_id: int, db: Session = Depends(get_db)):
    """获取用户连续学习状态。"""
    streak_orm = _get_or_create_streak(db, user_id)
    return StreakResponse(
        streak_count=streak_orm.streak_count,
        max_streak=streak_orm.max_streak,
        protections=streak_orm.protections,
        last_study_date=streak_orm.last_study_date,
    )


@router.post("/{user_id}/streak", response_model=StreakUpdateResponse)
def update_streak(
    user_id: int,
    req: UpdateStreakRequest,
    db: Session = Depends(get_db),
    game_engine: GamificationEngine = Depends(get_gamification_engine),
):
    """更新连续学习天数。"""
    streak_orm = _get_or_create_streak(db, user_id)
    streak = StreakInfo.from_orm(streak_orm)

    updated_streak, message = game_engine.update_streak(streak, req.study_date)
    updated_streak.to_orm(streak_orm)

    streak_xp = game_engine.calculate_streak_xp(updated_streak)

    db.commit()
    db.refresh(streak_orm)

    return StreakUpdateResponse(
        streak=StreakResponse(
            streak_count=streak_orm.streak_count,
            max_streak=streak_orm.max_streak,
            protections=streak_orm.protections,
            last_study_date=streak_orm.last_study_date,
        ),
        message=message,
        streak_xp=streak_xp,
    )


@router.get("/{user_id}/level", response_model=LevelInfoResponse)
def get_level(
    user_id: int,
    db: Session = Depends(get_db),
    game_engine: GamificationEngine = Depends(get_gamification_engine),
):
    """获取用户等级信息。"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 的画像不存在",
        )

    level_info = game_engine.calculate_level(profile.total_xp)
    return LevelInfoResponse(
        level=level_info.level,
        current_level_xp=level_info.current_level_xp,
        next_level_xp=level_info.next_level_xp,
        progress=level_info.progress,
    )


@router.get("/{user_id}/achievements", response_model=list[AchievementResponse])
def get_achievements(user_id: int, db: Session = Depends(get_db)):
    """获取成就列表（含解锁状态）。"""
    all_achievements = db.query(Achievement).all()
    unlocked_ids = {
        ua.achievement_id
        for ua in db.query(UserAchievement)
        .filter(UserAchievement.user_id == user_id)
        .all()
    }

    result = []
    for ach in all_achievements:
        result.append(
            AchievementResponse(
                code=ach.code,
                name=ach.name,
                description=ach.description,
                category=ach.category,
                xp_reward=ach.xp_reward,
                unlocked=ach.id in unlocked_ids,
            )
        )
    return result


@router.post("/{user_id}/achievements", response_model=list[AchievementResponse])
def check_achievements(
    user_id: int,
    db: Session = Depends(get_db),
    game_engine: GamificationEngine = Depends(get_gamification_engine),
):
    """检查并解锁成就。"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 的画像不存在",
        )

    streak_orm = _get_or_create_streak(db, user_id)

    all_achievements = db.query(Achievement).all()
    unlocked_ids = {
        ua.achievement_id
        for ua in db.query(UserAchievement)
        .filter(UserAchievement.user_id == user_id)
        .all()
    }

    user_stats = {
        "total_xp": profile.total_xp,
        "streak_days": streak_orm.streak_count,
    }

    achievement_defs = [
        {
            "code": a.code,
            "condition_type": a.condition_type,
            "condition_value": a.condition_value,
            "xp_reward": a.xp_reward,
        }
        for a in all_achievements
    ]

    check_result = game_engine.check_achievements(
        user_stats=user_stats,
        unlocked_codes={a.code for a in all_achievements if a.id in unlocked_ids},
        achievement_defs=achievement_defs,
    )

    # 解锁新成就
    newly_unlocked_codes = set(check_result.unlocked_codes)
    for ach in all_achievements:
        if ach.code in newly_unlocked_codes and ach.id not in unlocked_ids:
            db.add(UserAchievement(user_id=user_id, achievement_id=ach.id))

    if check_result.total_xp_reward > 0:
        profile.total_xp += check_result.total_xp_reward

    db.commit()

    # 返回全部成就状态
    return get_achievements(user_id, db)
