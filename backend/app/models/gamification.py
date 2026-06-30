"""
游戏化模型（阶段5 游戏化激励层使用）。

业务规范：
- 成就系统：定义可解锁的成就，用户达成条件后解锁
- 连续学习（Streak）：记录用户连续学习天数，配保护机制防止中断打击积极性
- 经验值和等级：在 UserProfile 中记录 total_xp 和 current_level
"""
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Achievement(Base):
    """
    成就定义。

    condition_type:
    - total_xp: 累计经验值达到阈值
    - streak_days: 连续学习天数达到阈值
    - correct_count: 累计正确答题数
    - subject_mastery: 某科目掌握度达到阈值
    - questions_answered: 累计答题数
    """

    __tablename__ = "achievements"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # categories: learning / streak / mastery / special

    condition_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_value: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserAchievement(Base):
    """用户已解锁的成就记录。"""

    __tablename__ = "user_achievements"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )


class UserStreak(Base):
    """
    用户连续学习记录。

    业务规范：
    - streak_count: 当前连续学习天数
    - max_streak: 历史最高连续天数
    - protections: 保护卡数量，断签时可消耗一张保护断签
    - last_study_date: 最近学习日期，用于判断是否断签
    """

    __tablename__ = "user_streaks"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    protections: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_study_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
