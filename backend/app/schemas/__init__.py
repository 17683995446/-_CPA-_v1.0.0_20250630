"""
Pydantic Schema 汇总导入。

架构规范：
- 所有 API 请求/响应模型在此统一导入
- Schema 层与 ORM Model 层分离，遵循单一职责原则
"""
from app.schemas.common import ApiResponse, MessageResponse, PaginatedResponse, error, not_found, success
from app.schemas.gamification import (
    AchievementResponse,
    LevelInfoResponse,
    StreakResponse,
    StreakUpdateResponse,
    UpdateStreakRequest,
)
from app.schemas.journal import (
    JournalEntryLineRequest,
    JournalValidationRequest,
    JournalValidationResponse,
)
from app.schemas.knowledge import (
    KnowledgeEdgeResponse,
    KnowledgeGraphResponse,
    KnowledgePointCreate,
    KnowledgePointResponse,
    LearningPathResponse,
)
from app.schemas.mastery import (
    MasteryResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.schemas.question import (
    GenerateQuestionRequest,
    QuestionOptionResponse,
    QuestionResponse,
)
from app.schemas.review import (
    DueCardsResponse,
    ReviewCardResponse,
    SubmitReviewRequest,
    SubmitReviewResponse,
)
from app.schemas.study import (
    StartSessionRequest,
    StudySessionResponse,
    UpdateSessionRequest,
)
from app.schemas.user import (
    UserCreate,
    UserProfileResponse,
    UserProfileUpdate,
    UserResponse,
)

__all__ = [
    # common
    "ApiResponse",
    "MessageResponse",
    "PaginatedResponse",
    "success",
    "error",
    "not_found",
    # user
    "UserCreate",
    "UserResponse",
    "UserProfileResponse",
    "UserProfileUpdate",
    # knowledge
    "KnowledgePointCreate",
    "KnowledgePointResponse",
    "KnowledgeEdgeResponse",
    "KnowledgeGraphResponse",
    "LearningPathResponse",
    # question
    "GenerateQuestionRequest",
    "QuestionResponse",
    "QuestionOptionResponse",
    # review
    "ReviewCardResponse",
    "DueCardsResponse",
    "SubmitReviewRequest",
    "SubmitReviewResponse",
    # mastery
    "MasteryResponse",
    "SubmitAnswerRequest",
    "SubmitAnswerResponse",
    # gamification
    "StreakResponse",
    "StreakUpdateResponse",
    "LevelInfoResponse",
    "AchievementResponse",
    "UpdateStreakRequest",
    # journal
    "JournalEntryLineRequest",
    "JournalValidationRequest",
    "JournalValidationResponse",
    # study
    "StartSessionRequest",
    "StudySessionResponse",
    "UpdateSessionRequest",
]
