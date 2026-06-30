"""
API 依赖注入。

架构规范：
- 引擎实例通过依赖注入提供给路由，确保单例复用
- 数据库会话通过 FastAPI Depends 注入，每请求独立
"""
import random

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.engines.bkt import BKTEngine
from app.engines.fsrs import FSRSEngine
from app.engines.gamification import GamificationEngine
from app.engines.journal_validator import JournalEntryValidator
from app.engines.question_gen import QuestionGenerator


# ========== 引擎单例 ==========

_fsrs_engine: FSRSEngine | None = None
_bkt_engine: BKTEngine | None = None
_question_generator: QuestionGenerator | None = None
_journal_validator: JournalEntryValidator | None = None
_gamification_engine: GamificationEngine | None = None


def get_fsrs_engine() -> FSRSEngine:
    """获取 FSRS 引擎单例。"""
    global _fsrs_engine
    if _fsrs_engine is None:
        _fsrs_engine = FSRSEngine(
            request_retention=settings.FSRS_REQUEST_RETENTION,
            maximum_interval=settings.FSRS_MAXIMUM_INTERVAL,
        )
    return _fsrs_engine


def get_bkt_engine() -> BKTEngine:
    """获取 BKT 引擎单例。"""
    global _bkt_engine
    if _bkt_engine is None:
        _bkt_engine = BKTEngine(
            default_p_init=settings.BKT_DEFAULT_P_INIT,
            default_p_transit=settings.BKT_DEFAULT_P_TRANSIT,
            default_p_guess=settings.BKT_DEFAULT_P_GUESS,
            default_p_slip=settings.BKT_DEFAULT_P_SLIP,
        )
    return _bkt_engine


def get_question_generator() -> QuestionGenerator:
    """获取出题引擎单例。"""
    global _question_generator
    if _question_generator is None:
        _question_generator = QuestionGenerator()
    return _question_generator


def get_journal_validator() -> JournalEntryValidator:
    """获取分录判错引擎单例。"""
    global _journal_validator
    if _journal_validator is None:
        _journal_validator = JournalEntryValidator()
    return _journal_validator


def get_gamification_engine() -> GamificationEngine:
    """获取游戏化引擎单例，参数从 config 注入以消除配置双源。"""
    global _gamification_engine
    if _gamification_engine is None:
        _gamification_engine = GamificationEngine(
            xp_per_correct=settings.XP_PER_CORRECT,
            xp_per_streak_day=settings.XP_PER_STREAK_DAY,
            streak_protection_default=settings.STREAK_PROTECTION_DEFAULT,
        )
    return _gamification_engine


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
