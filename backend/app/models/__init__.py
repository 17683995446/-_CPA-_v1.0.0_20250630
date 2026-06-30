"""
ORM 模型汇总导入。

遵循架构规范：所有模型在此统一导入，确保 Base.metadata 包含全部表。
"""
from app.models.gamification import Achievement, UserAchievement, UserStreak
from app.models.knowledge import KnowledgeEdge, KnowledgePoint
from app.models.mastery import UserMastery
from app.models.question import Question, QuestionOption
from app.models.review import ReviewCard, ReviewLog
from app.models.study import StudySession
from app.models.user import User, UserBehaviorLog, UserProfile

__all__ = [
    "User",
    "UserProfile",
    "UserBehaviorLog",
    "KnowledgePoint",
    "KnowledgeEdge",
    "Question",
    "QuestionOption",
    "ReviewCard",
    "ReviewLog",
    "StudySession",
    "UserMastery",
    "Achievement",
    "UserAchievement",
    "UserStreak",
]
