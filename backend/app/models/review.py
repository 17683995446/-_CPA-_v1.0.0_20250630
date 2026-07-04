"""
复习卡片模型（FSRS 间隔重复引擎使用）。

第一性原理：间隔重复的核心是「记忆稳定性」随复习增强、随时间衰减。
FSRS 用 stability（稳定性）和 difficulty（难度）两个变量描述卡片状态，
据此计算下次复习时间。

业务规范：
- 每张卡片关联一道题目和一个用户
- 卡片状态记录 FSRS 的核心变量
- 复习日志记录每次评分及前后状态变化，用于算法验证和参数优化
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewCard(Base):
    """
    FSRS 复习卡片。

    核心变量（FSRS-4.5/5 标准）：
    - stability: 记忆稳定性（天），值越大遗忘越慢
    - difficulty: 卡片难度 1-10
    - due: 下次到期日期
    - reps: 已复习次数
    - lapses: 遗忘次数（评为 Again 的次数）
    - state: 卡片状态 new / learning / review / relearning
    """

    __tablename__ = "review_cards"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )

    # FSRS 核心变量
    stability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    due: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_review: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), default="new", nullable=False
    )  # new / learning / review / relearning

    # 关联
    logs: Mapped[list["ReviewLog"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class ReviewLog(Base):
    """
    复习日志：记录每次复习的完整上下文。

    用于：
    - FSRS 参数优化（通过历史日志反推最优权重）
    - 算法正确性验证
    - 用户学习行为分析
    """

    __tablename__ = "review_logs"

    card_id: Mapped[int] = mapped_column(
        ForeignKey("review_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 评分：1(Again) / 2(Hard) / 3(Good) / 4(Easy)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    # 复习时间
    review_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 距离上次复习的天数
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 本次安排的间隔天数
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 复习前后的卡片状态
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    stability_before: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    difficulty_before: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stability_after: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    difficulty_after: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 关联
    card: Mapped["ReviewCard"] = relationship(back_populates="logs")
