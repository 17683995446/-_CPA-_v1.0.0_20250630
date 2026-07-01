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
    """题目选项响应。注意：不返回 is_correct 字段，防止前端泄露答案。"""

    label: str
    content: str


class QuestionResponse(BaseModel):
    """题目响应。"""

    question_type: str
    content: str
    answer: str
    explanation: str
    simple_explanation: Optional[str] = None
    mnemonic: Optional[str] = None
    study_tip: Optional[str] = None
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

    关键修复：answer 字段从 is_correct 派生，而非信任 q.answer 文本。
    这确保了即使选项被打乱、label 被重排，返回前端的答案键始终正确。
    """
    sorted_options = sorted(q.options, key=lambda o: o.label)

    # 从 is_correct 派生正确答案，确保与选项标签一致
    correct_labels = [o.label for o in sorted_options if o.is_correct]
    if q.question_type == "judgment":
        # 判断题：answer 是内容文本（"正确"/"错误"）
        correct_opt = next((o for o in sorted_options if o.is_correct), None)
        derived_answer = correct_opt.content if correct_opt else q.answer
    elif q.question_type == "multiple_choice":
        # 多选题：answer 是多标签拼接（如 "AC"）
        derived_answer = "".join(correct_labels) if correct_labels else q.answer
    elif correct_labels:
        # 单选题等：answer 是单个标签（如 "B"）
        derived_answer = correct_labels[0]
    else:
        # 兜底：journal_entry / tbs 等无选项题型，保留原始 answer
        derived_answer = q.answer

    return QuestionResponse(
        question_type=q.question_type,
        content=q.content,
        answer=derived_answer,
        explanation=q.explanation or "",
        simple_explanation=getattr(q, "simple_explanation", None),
        mnemonic=getattr(q, "mnemonic", None),
        study_tip=getattr(q, "study_tip", None),
        difficulty=q.difficulty,
        options=[
            QuestionOptionResponse(
                label=o.label,
                content=o.content,
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
