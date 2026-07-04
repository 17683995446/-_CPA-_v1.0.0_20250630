"""
用户领域模型。

业务规范：
- CPA 备考用户有明确的目标考试日期和每日学习目标
- 用户画像记录偏好科目、当前等级、累计经验值
- 行为日志用于疲劳检测和自适应难度（阶段5 使用）
"""
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """用户主表。"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 关联
    profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserProfile(Base):
    """用户画像：备考计划与游戏化状态。"""

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # 备考计划
    target_exam_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # 偏好科目（JSON 字符串存储科目列表）
    preferred_subjects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 游戏化状态（阶段5 使用）
    current_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 关联
    user: Mapped["User"] = relationship(back_populates="profile")


class UserBehaviorLog(Base):
    """
    用户行为日志。

    记录每次学习交互的原始事件，用于：
    - 疲劳检测（阶段5 自适应难度）
    - 错误模式分析
    - 学习时间分布分析
    """

    __tablename__ = "user_behavior_logs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # answer / review / session_start / session_end
    event_data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # 记录交互时的响应时间（毫秒），用于疲劳检测
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
