"""
核心算法引擎层。

所有引擎使用纯 dataclass 承载状态，通过 from_orm/to_orm 与 ORM 模型互转。
引擎不直接依赖数据库，可独立单元测试。
"""
from app.engines.bkt import BKTEngine, BKTResult, MasteryState
from app.engines.fsrs import Card, CardState, FSRSEngine, Rating, ReviewResult
from app.engines.gamification import (
    AchievementCategory,
    AchievementCheckResult,
    FlowState,
    GamificationEngine,
    LevelInfo,
    StreakInfo,
    XPResult,
)
from app.engines.journal_validator import (
    AccountType,
    EntryDirection,
    ErrorType,
    JournalEntryLine,
    JournalEntryValidator,
    ValidationError,
    ValidationResult,
)
from app.engines.knowledge_graph import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    VisualizationData,
)
from app.engines.question_gen import QuestionGenerator

__all__ = [
    "BKTEngine",
    "BKTResult",
    "MasteryState",
    "Card",
    "CardState",
    "FSRSEngine",
    "Rating",
    "ReviewResult",
    "AchievementCategory",
    "AchievementCheckResult",
    "FlowState",
    "GamificationEngine",
    "LevelInfo",
    "StreakInfo",
    "XPResult",
    "AccountType",
    "EntryDirection",
    "ErrorType",
    "JournalEntryLine",
    "JournalEntryValidator",
    "ValidationError",
    "ValidationResult",
    "GraphEdge",
    "GraphNode",
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
    "VisualizationData",
    "QuestionGenerator",
]
