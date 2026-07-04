"""
API 依赖注入。

架构规范：
- 引擎实例通过 EngineContainer 集中管理，消除全局可变状态
- 数据库会话通过 FastAPI Depends 注入，每请求独立
- 所有 get_* 函数保持原有签名，确保路由层零改动兼容

设计原理：
全局变量 `_fsrs_engine` 等模式存在线程安全和测试隔离问题。
EngineContainer 将所有引擎实例封装在一个对象中，通过单一全局
容器引用管理生命周期，测试时可通过 reset_container() 重置。
"""
import threading

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.engines.bkt import BKTEngine
from app.engines.fsrs import FSRSEngine
from app.engines.gamification import GamificationEngine
from app.engines.journal_validator import JournalEntryValidator
from app.engines.question_gen import QuestionGenerator


class EngineContainer:
    """引擎实例容器，集中管理所有引擎的单例创建和生命周期。

    线程安全：通过 threading.Lock 保护初始化过程。
    可测试：通过 reset() 方法清除所有实例，支持测试隔离。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fsrs: FSRSEngine | None = None
        self._bkt: BKTEngine | None = None
        self._question_gen: QuestionGenerator | None = None
        self._journal_validator: JournalEntryValidator | None = None
        self._gamification: GamificationEngine | None = None

    @property
    def fsrs(self) -> FSRSEngine:
        if self._fsrs is None:
            with self._lock:
                if self._fsrs is None:
                    self._fsrs = FSRSEngine(
                        request_retention=settings.FSRS_REQUEST_RETENTION,
                        maximum_interval=settings.FSRS_MAXIMUM_INTERVAL,
                    )
        return self._fsrs

    @property
    def bkt(self) -> BKTEngine:
        if self._bkt is None:
            with self._lock:
                if self._bkt is None:
                    self._bkt = BKTEngine(
                        default_p_init=settings.BKT_DEFAULT_P_INIT,
                        default_p_transit=settings.BKT_DEFAULT_P_TRANSIT,
                        default_p_guess=settings.BKT_DEFAULT_P_GUESS,
                        default_p_slip=settings.BKT_DEFAULT_P_SLIP,
                    )
        return self._bkt

    @property
    def question_generator(self) -> QuestionGenerator:
        if self._question_gen is None:
            with self._lock:
                if self._question_gen is None:
                    self._question_gen = QuestionGenerator()
        return self._question_gen

    @property
    def journal_validator(self) -> JournalEntryValidator:
        if self._journal_validator is None:
            with self._lock:
                if self._journal_validator is None:
                    self._journal_validator = JournalEntryValidator()
        return self._journal_validator

    @property
    def gamification(self) -> GamificationEngine:
        if self._gamification is None:
            with self._lock:
                if self._gamification is None:
                    engine = GamificationEngine(
                        xp_per_correct=settings.XP_PER_CORRECT,
                        xp_per_streak_day=settings.XP_PER_STREAK_DAY,
                        streak_protection_default=settings.STREAK_PROTECTION_DEFAULT,
                        critical_chance=settings.GAMIFICATION_CRITICAL_CHANCE,
                        critical_multiplier=settings.GAMIFICATION_CRITICAL_MULTIPLIER,
                        base_level_xp=settings.GAMIFICATION_BASE_LEVEL_XP,
                        level_growth_rate=settings.GAMIFICATION_LEVEL_GROWTH_RATE,
                        streak_protection_max=settings.GAMIFICATION_STREAK_PROTECTION_MAX,
                    )
                    # XP_STREAK_BONUS_THRESHOLD 仍为类属性（不影响隔离）
                    engine.XP_STREAK_BONUS_THRESHOLD = settings.GAMIFICATION_STREAK_BONUS_THRESHOLD
                    self._gamification = engine
        return self._gamification

    def reset(self) -> None:
        """清除所有引擎实例，用于测试隔离。"""
        with self._lock:
            self._fsrs = None
            self._bkt = None
            self._question_gen = None
            self._journal_validator = None
            self._gamification = None


# 全局容器实例（唯一全局可变状态，通过 reset() 可控）
_container: EngineContainer = EngineContainer()


def get_container() -> EngineContainer:
    """获取引擎容器实例。测试时可通过 app.dependency_overrides 替换。"""
    return _container


def reset_container() -> None:
    """重置引擎容器，清除所有单例。用于测试。"""
    _container.reset()


# ========== FastAPI 依赖函数（保持原有签名，路由层零改动） ==========


def get_fsrs_engine() -> FSRSEngine:
    """获取 FSRS 引擎单例。"""
    return _container.fsrs


def get_bkt_engine() -> BKTEngine:
    """获取 BKT 引擎单例。"""
    return _container.bkt


def get_question_generator() -> QuestionGenerator:
    """获取出题引擎单例。"""
    return _container.question_generator


def get_journal_validator() -> JournalEntryValidator:
    """获取分录判错引擎单例。"""
    return _container.journal_validator


def get_gamification_engine() -> GamificationEngine:
    """获取游戏化引擎单例。"""
    return _container.gamification


# ========== 通用依赖 ==========


def get_user_or_404(
    user_id: int,
    db: Session = Depends(get_db),
):
    """根据 ID 获取用户，不存在则返回 404。"""
    from app.models import User

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 不存在",
        )
    return user
