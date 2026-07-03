"""
题目领域模型。

业务规范：
- CPA 题型包括：单选、多选、判断、综合题（TBS）、会计分录题
- 每道题关联一个知识点，用于知识追踪和间隔重复
- 题目来源标记（真题/模拟/AI生成），用于质量评估
"""
from __future__ import annotations
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Question(Base):
    """
    题目。

    question_type 取值：
    - single_choice: 单选题
    - multiple_choice: 多选题
    - judgment: 判断题
    - tbs: 综合题（Testlet-Based Scenario）
    - journal_entry: 会计分录题（阶段6 判错引擎使用）
    """

    __tablename__ = "questions"

    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # 题干
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 标准答案（分录题存 JSON 结构化数据，其他题型存选项标识）
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # 解析（详细解析）
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 通俗易懂简洁解释
    simple_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 记忆口诀/记忆诀窍
    mnemonic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 小贴士（学习建议）
    study_tip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 难度 1-5
    difficulty: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # 来源：past_exam（真题）/ mock（模拟）/ ai_generated（AI生成）
    source: Mapped[str] = mapped_column(String(32), default="mock", nullable=False)

    # 真题年份（仅 source=past_exam 时有值），如 2021
    exam_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 考点说明：本题考查的具体考点
    exam_point: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 关联
    knowledge_point: Mapped["KnowledgePoint"] = relationship(  # noqa: F821
        back_populates="questions"
    )
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionOption(Base):
    """题目选项（仅选择题使用）。"""

    __tablename__ = "question_options"

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(8), nullable=False)  # A / B / C / D
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 关联
    question: Mapped["Question"] = relationship(back_populates="options")
