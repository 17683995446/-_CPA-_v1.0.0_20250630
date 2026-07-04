"""
知识掌握度模型（BKT 知识追踪引擎使用）。

第一性原理：知识掌握是一个概率，而非二元状态。
BKT 用 4 个参数描述知识掌握的动态过程：
- p_known: 当前掌握概率
- p_transit: 未掌握→掌握的转移概率（学习速率）
- p_guess: 未掌握但猜对的概率
- p_slip: 已掌握但答错的概率

业务规范：
- 每个用户对每个知识点维护一组 BKT 参数
- 每次答题后更新 p_known
- p_known 是推荐系统和自适应难度的基础信号
"""
from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserMastery(Base):
    """
    用户对知识点的掌握度（BKT 参数）。

    唯一约束：(user_id, knowledge_point_id)
    """

    __tablename__ = "user_masteries"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_user_kp"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )

    # BKT 四参数
    p_known: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    p_transit: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    p_guess: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    p_slip: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)

    # 该知识点的累计答题数和正确数
    total_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
