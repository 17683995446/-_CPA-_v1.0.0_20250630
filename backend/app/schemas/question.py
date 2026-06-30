"""
题目相关 Schema。

业务规范：
- 题目可由 AI 引擎按知识点和难度动态生成
- 题型包括：单选、多选、判断、综合题（TBS）、会计分录题
"""
from typing import Optional

from pydantic import BaseModel, Field


class GenerateQuestionRequest(BaseModel):
    """出题请求。"""

    knowledge_point_code: str = Field(..., description="知识点编码")
    difficulty: int = Field(3, ge=1, le=5, description="目标难度 1-5")
    seed: Optional[int] = Field(None, description="随机种子（用于可复现测试）")


class QuestionOptionResponse(BaseModel):
    """题目选项响应。"""

    label: str
    content: str
    is_correct: bool


class QuestionResponse(BaseModel):
    """题目响应。"""

    question_type: str
    content: str
    answer: str
    explanation: str
    difficulty: int
    options: list[QuestionOptionResponse] = Field(default_factory=list)
    knowledge_point_code: Optional[str] = None
    cognitive_level: str = "understand"
    source: str = "ai_generated"
    variant_id: str = ""
    exam_year: Optional[int] = None
    exam_point: Optional[str] = None


def question_to_response(q: "Question") -> QuestionResponse:
    """
    将 ORM Question 模型转换为 QuestionResponse。

    消除路由层4处重复的 QuestionResponse 构造逻辑。
    选项按 label 排序，确保前端始终显示 A/B/C/D 顺序。
    """
    sorted_options = sorted(q.options, key=lambda o: o.label)
    return QuestionResponse(
        question_type=q.question_type,
        content=q.content,
        answer=q.answer,
        explanation=q.explanation or "",
        difficulty=q.difficulty,
        options=[
            QuestionOptionResponse(
                label=o.label,
                content=o.content,
                is_correct=o.is_correct,
            )
            for o in sorted_options
        ],
        knowledge_point_code="",
        cognitive_level="understand",
        source=q.source,
        variant_id=f"db_{q.id}",
        exam_year=q.exam_year,
        exam_point=q.exam_point,
    )
