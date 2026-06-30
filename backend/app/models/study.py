"""
学习会话模型。

业务规范：
- 一次学习会话是用户连续学习的时间段
- 记录会话内的答题数、正确率、获得经验值
- 用于学习时长分析和疲劳检测
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StudySession(Base):
    """学习会话：用户一次连续学习的时间段。"""

    __tablename__ = "study_sessions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    questions_answered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
