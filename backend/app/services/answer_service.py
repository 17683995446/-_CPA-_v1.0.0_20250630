"""
答题服务层。

第一性原理：一次答题应同时驱动三个引擎（BKT + FSRS + 游戏化），
这是 CPA 学习系统的核心循环。将此编排逻辑从路由层抽离为独立 Service，
使路由层保持薄、业务逻辑可独立测试。

架构规范：
- Service 接收引擎实例和 DB 会话，编排跨引擎协作
- 不直接依赖 FastAPI（无 HTTPException），通过返回值或异常传递结果
- 可被路由层注入，也可被其他 Service 或定时任务复用
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.engines.bkt import BKTEngine, MasteryState
from app.engines.fsrs import Card, FSRSEngine, Rating
from app.engines.gamification import GamificationEngine
from app.models import ReviewCard, User, UserMastery, UserProfile


@dataclass
class AnswerResult:
    """答题结果（跨引擎汇总）。"""

    # BKT
    p_known_before: float
    p_known_after: float
    mastery_level: str
    recommended_difficulty: int

    # FSRS
    fsrs_updated: bool
    next_due: Optional[str]
    interval: Optional[int]
    stability_after: Optional[float]

    # 游戏化
    xp_earned: int
    xp_reason: str
    is_critical: bool
    total_xp: int
    current_level: int
    level_up: Optional[int]
    should_celebrate: bool


class AnswerService:
    """
    答题编排服务。

    一次答题同时驱动：
    1. BKT 更新知识掌握度（p_known）
    2. FSRS 更新复习卡片调度（如有卡片）
    3. 游戏化计算 XP 奖励、检查等级和成就
    """

    def __init__(
        self,
        bkt_engine: BKTEngine,
        fsrs_engine: FSRSEngine,
        game_engine: GamificationEngine,
    ):
        self.bkt_engine = bkt_engine
        self.fsrs_engine = fsrs_engine
        self.game_engine = game_engine

    @staticmethod
    def _get_or_create_mastery(
        db: Session, user_id: int, kp_id: int, bkt_engine: BKTEngine
    ) -> UserMastery:
        """获取或创建用户的知识点掌握度记录。"""
        mastery_orm = (
            db.query(UserMastery)
            .filter(
                UserMastery.user_id == user_id,
                UserMastery.knowledge_point_id == kp_id,
            )
            .first()
        )
        if mastery_orm is None:
            mastery_orm = UserMastery(
                user_id=user_id,
                knowledge_point_id=kp_id,
                p_known=bkt_engine.defaults.p_known,
                p_transit=bkt_engine.defaults.p_transit,
                p_guess=bkt_engine.defaults.p_guess,
                p_slip=bkt_engine.defaults.p_slip,
            )
            db.add(mastery_orm)
            db.flush()
        return mastery_orm

    def submit(
        self,
        db: Session,
        user: User,
        knowledge_point_id: int,
        is_correct: bool,
        difficulty: int,
        question_id: Optional[int] = None,
        rating: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> AnswerResult:
        """
        执行答题核心循环。

        参数：
        - db: 数据库会话
        - user: 已验证存在的用户对象
        - knowledge_point_id: 知识点 ID
        - is_correct: 是否答对
        - difficulty: 题目难度 1-5
        - question_id: 关联题目 ID（可选，用于 FSRS 卡片更新）
        - rating: FSRS 评分 1-4（可选，不传则根据 is_correct 推断）
        - seed: 随机种子（可选，用于可复现测试）

        返回：AnswerResult 汇总对象
        """
        user_id = user.id

        # --- 1. BKT 更新 ---
        mastery_orm = self._get_or_create_mastery(
            db, user_id, knowledge_point_id, self.bkt_engine
        )
        mastery = MasteryState.from_orm(mastery_orm)
        p_known_before = mastery.p_known

        self.bkt_engine.update(mastery, is_correct=is_correct)
        mastery.to_orm(mastery_orm)

        mastery_orm.total_answers += 1
        if is_correct:
            mastery_orm.correct_answers += 1

        # --- 2. FSRS 更新（如有关联卡片）---
        fsrs_updated = False
        next_due = None
        interval = None
        stability_after = None

        if question_id is not None:
            card_orm = (
                db.query(ReviewCard)
                .filter(
                    ReviewCard.user_id == user_id,
                    ReviewCard.question_id == question_id,
                )
                .first()
            )
            # Get-or-create: 答题时自动为题目创建复习卡片
            if card_orm is None:
                card_orm = ReviewCard(
                    user_id=user_id,
                    question_id=question_id,
                    knowledge_point_id=knowledge_point_id,
                    due=date.today(),
                )
                db.add(card_orm)
                db.flush()

            card = Card.from_orm(card_orm)
            if rating is not None:
                fsrs_rating = Rating(rating)
            else:
                fsrs_rating = Rating.GOOD if is_correct else Rating.AGAIN

            now = datetime.now()
            fsrs_result = self.fsrs_engine.review(card, fsrs_rating, now)
            card.to_orm(card_orm)

            fsrs_updated = True
            next_due = card_orm.due.isoformat()
            interval = fsrs_result.interval
            stability_after = fsrs_result.stability_after

        # --- 3. 游戏化：XP 计算 ---
        import random as _random

        if seed is not None:
            game_engine = GamificationEngine(rng=_random.Random(seed))
        else:
            game_engine = self.game_engine

        xp_result = game_engine.calculate_xp(
            is_correct=is_correct,
            difficulty=difficulty,
        )

        profile = (
            db.query(UserProfile)
            .filter(UserProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
            db.flush()

        old_total_xp = profile.total_xp
        profile.total_xp += xp_result.total_xp

        level_up = game_engine.check_level_up(old_total_xp, profile.total_xp)
        if level_up is not None:
            profile.current_level = level_up

        should_celebrate = game_engine.should_celebrate(
            xp_result=xp_result,
            level_up=level_up,
        )

        db.commit()
        db.refresh(profile)

        return AnswerResult(
            p_known_before=p_known_before,
            p_known_after=mastery.p_known,
            mastery_level=self.bkt_engine.mastery_level(mastery),
            recommended_difficulty=self.bkt_engine.recommend_difficulty(mastery),
            fsrs_updated=fsrs_updated,
            next_due=next_due,
            interval=interval,
            stability_after=stability_after,
            xp_earned=xp_result.total_xp,
            xp_reason=xp_result.reason,
            is_critical=xp_result.is_critical,
            total_xp=profile.total_xp,
            current_level=profile.current_level,
            level_up=level_up,
            should_celebrate=should_celebrate,
        )
