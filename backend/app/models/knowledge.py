"""
知识领域模型。

业务规范：
- CPA 知识体系按「科目 → 章节 → 知识点」三级层次组织
- 知识点之间存在前置依赖关系（如「借贷记账法」是「资产核算」的前置）
- 知识图谱的边记录关联类型，支持跨章节关联
"""
from __future__ import annotations
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgePoint(Base):
    """
    知识点：知识图谱中的节点。

    对应 CPA 考纲中的最小知识单元，如「存货的初始计量」。
    """

    __tablename__ = "knowledge_points"

    # 知识点编码，如 "ACC-01-03" 表示会计科目第1章第3个知识点
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 所属科目（取值见 config.CPA_SUBJECTS）
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    # 章节名
    chapter: Mapped[str] = mapped_column(String(64), nullable=False)

    # 知识点描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 难度等级 1-5，5 为最难
    difficulty: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # 默认掌握概率（BKT 初始值）
    mastery_default: Mapped[float] = mapped_column(
        Float, default=0.1, nullable=False
    )

    # 关联
    questions: Mapped[list["Question"]] = relationship(
        back_populates="knowledge_point"
    )


class KnowledgeEdge(Base):
    """
    知识图谱的边：知识点之间的关联关系。

    relation_type:
    - prerequisite: 前置依赖（学习 B 前需先学 A）
    - related: 相关联（A 和 B 有交叉内容）
    - parent: 父子包含（A 包含 B）
    """

    __tablename__ = "knowledge_edges"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), default="prerequisite", nullable=False
    )
