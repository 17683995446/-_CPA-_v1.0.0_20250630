"""
BKT 知识追踪相关 Schema。

业务规范：
- 每个用户对每个知识点维护独立的 BKT 参数
- 答题后同时更新 BKT 掌握度和 FSRS 复习调度
- 掌握度是自适应难度推荐的基础信号
"""
from typing import Optional

from pydantic import BaseModel, Field


class MasteryResponse(BaseModel):
    """掌握度响应。"""

    knowledge_point_id: int
    p_known: float
    p_transit: float
    p_guess: float
    p_slip: float
    total_answers: int
    correct_answers: int
    mastery_level: str  # unknown / learning / mastering / mastered
    recommended_difficulty: int


class MasteryItemResponse(BaseModel):
    """单个知识点的掌握度摘要（批量查询用）。

    包含知识点基本信息 + BKT 掌握度，供前端知识可视化直接渲染。
    """

    knowledge_point_id: int
    knowledge_point_code: str
    knowledge_point_name: str
    subject: str
    chapter: str
    difficulty: int
    p_known: float
    mastery_level: str
    total_answers: int
    correct_answers: int
    recommended_difficulty: int


class BatchMasteryResponse(BaseModel):
    """用户所有知识点掌握度批量响应。

    一次请求返回全部知识点的掌握度，避免前端 N+1 调用。
    未答题的知识点返回 BKT 默认值（p_known=0.1, level=unknown）。
    """

    user_id: int
    total_kps: int
    answered_kps: int
    items: list[MasteryItemResponse]


class SubmitAnswerRequest(BaseModel):
    """提交答题请求（集成 BKT + FSRS + 游戏化）。"""

    knowledge_point_id: int = Field(..., description="知识点 ID")
    question_id: Optional[int] = Field(None, description="题目 ID（如有关联卡片）")
    is_correct: bool = Field(..., description="是否答对")
    difficulty: int = Field(3, ge=1, le=5, description="题目难度")
    rating: Optional[int] = Field(
        None, ge=1, le=4, description="FSRS 评分（未提供则根据 is_correct 推断）"
    )
    seed: Optional[int] = Field(None, description="随机种子（用于 XP 可复现测试）")


class SubmitAnswerResponse(BaseModel):
    """答题结果响应（集成 BKT + FSRS + XP）。"""

    # BKT 结果
    p_known_before: float
    p_known_after: float
    mastery_level: str
    recommended_difficulty: int

    # FSRS 结果（如有卡片）
    fsrs_updated: bool = False
    next_due: Optional[str] = None
    interval: Optional[int] = None
    stability_after: Optional[float] = None

    # 游戏化结果
    xp_earned: int = 0
    xp_reason: str = ""
    is_critical: bool = False
    total_xp: int = 0
    current_level: int = 1
    level_up: Optional[int] = None
    should_celebrate: bool = False
