"""
AI 出题与题库路由。

业务规范：
- 按知识点编码和难度动态生成题目（AI 引擎）
- 也可从题库中获取已录入的真题/模拟题
- 支持随机种子保证测试可复现
- 生成的题目包含选项、答案、解析

架构规范：
- ORM → Response 转换统一使用 question_to_response()，消除重复
"""
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_question_generator
from app.db.session import get_db
from app.engines.question_gen import QuestionGenerator
from app.models import KnowledgePoint, Question
from app.schemas.question import (
    GenerateQuestionRequest,
    QuestionResponse,
    question_to_response,
)

router = APIRouter(prefix="/api/questions", tags=["AI 出题"])


@router.get("/by-kp/{kp_id}", response_model=list[QuestionResponse])
def get_questions_by_kp(
    kp_id: int,
    db: Session = Depends(get_db),
) -> list[QuestionResponse]:
    """获取知识点关联的题库题目。"""
    questions = db.query(Question).filter(Question.knowledge_point_id == kp_id).all()
    return [question_to_response(q) for q in questions]


@router.get("/random", response_model=QuestionResponse)
def get_random_question(
    subject: str | None = None,
    db: Session = Depends(get_db),
) -> QuestionResponse:
    """随机获取一道题库题目。"""
    query = db.query(Question)
    if subject:
        query = query.join(KnowledgePoint).filter(KnowledgePoint.subject == subject)

    questions = query.all()
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题库中暂无题目",
        )

    q = random.choice(questions)
    return question_to_response(q)


@router.post("/generate", response_model=QuestionResponse)
def generate_question(
    req: GenerateQuestionRequest,
    generator: QuestionGenerator = Depends(get_question_generator),
) -> QuestionResponse:
    """按知识点和难度生成一道题目。"""
    rng = random.Random(req.seed) if req.seed is not None else None

    question = generator.generate_by_knowledge_point(
        req.knowledge_point_code,
        difficulty=req.difficulty,
        rng=rng,
    )

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识点 {req.knowledge_point_code} 无可用题目模板",
        )

    return question_to_response(question)


@router.post("/generate-variants", response_model=list[QuestionResponse])
def generate_variants(
    req: GenerateQuestionRequest,
    count: int = 3,
    generator: QuestionGenerator = Depends(get_question_generator),
) -> list[QuestionResponse]:
    """生成同一知识点的多个变体。"""
    template = None
    for t in generator.templates.values():
        if t.knowledge_point_code == req.knowledge_point_code:
            template = t
            break

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识点 {req.knowledge_point_code} 无可用题目模板",
        )

    rng = random.Random(req.seed) if req.seed is not None else None
    variants = generator.generate_variants(template, count=count, difficulty=req.difficulty, rng=rng)

    return [question_to_response(v) for v in variants]


@router.get("/templates", response_model=list[str])
def list_templates(
    generator: QuestionGenerator = Depends(get_question_generator),
) -> list[str]:
    """列出所有已注册的题目模板 ID。"""
    return generator.list_templates()


@router.get("/count")
def get_question_count(db: Session = Depends(get_db)) -> dict:
    """获取题库题目总数。"""
    return {"total": db.query(Question).count()}
