"""
LLM 分析相关 ORM 模型。

表设计：
    question_embeddings — 题目向量索引（相似题推荐用）
    error_analyses      — 错题归因记录
    study_reports       — 学习诊断报告
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class QuestionEmbedding(Base):
    """题目 embedding 向量，用于相似题推荐。

    每道题一条记录，存储其题干的 embedding 向量。
    向量以 JSON 字符串存储，加载时用 json.loads 还原为 list[float]。
    """
    __tablename__ = "question_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id"), unique=True, nullable=False, index=True)
    # 向量以 JSON 字符串存储："[0.012, -0.034, ...]"
    # 避免引入 pgvector 等扩展，保持 SQLite 兼容
    embedding_json = Column(Text, nullable=False)
    dim = Column(Integer, nullable=False)
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    question = relationship("Question", backref="embedding_row")


class ErrorAnalysis(Base):
    """错题归因分析记录。

    学生答错后，LLM 分析错误类型并给出建议。
    """
    __tablename__ = "error_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    # 学生选择的内容
    user_answer = Column(String(500), nullable=False)
    # LLM 归因的错误类型
    error_type = Column(String(50), nullable=False)
    # error_type 枚举值：
    # concept_confusion   — 概念混淆
    # calculation_error   — 计算失误
    # misreading          — 审题不清
    # memory_decay        — 记忆遗忘
    # method_wrong        — 方法选择错误
    # LLM 给出的建议
    suggestion = Column(Text, nullable=False)
    # LLM 给出的关联知识点提示
    related_concept = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="error_analyses")
    question = relationship("Question", backref="error_analyses")


class StudyReport(Base):
    """学习诊断报告。

    定期生成，基于 BKT 掌握度 + 答题模式。
    """
    __tablename__ = "study_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 报告类型：weekly / monthly / on_demand
    report_type = Column(String(20), nullable=False, default="weekly")
    # 报告内容（JSON 字符串，包含结构化诊断结果）
    content_json = Column(Text, nullable=False)
    # 报告摘要（用于列表展示）
    summary = Column(String(500), nullable=False)
    # 数据快照：报告生成时的关键指标
    total_questions = Column(Integer, nullable=False, default=0)
    accuracy_rate = Column(Float, nullable=False, default=0.0)
    weak_points_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="study_reports")
