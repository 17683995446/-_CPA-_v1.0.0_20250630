"""历年真题导入。"""
from sqlalchemy.orm import Session

from app.models import Question, QuestionOption


def _import_past_exams(db: Session, code_to_id: dict[str, int], past_exams: list[dict]) -> int:
    """
    导入历年真题到题库。

    参数：
        db: 数据库会话
        code_to_id: 知识点编码到ID的映射
        past_exams: 真题数据列表

    返回：成功导入的题目数量
    """
    count = 0
    for exam in past_exams:
        kp_id = code_to_id.get(exam["kp_code"])
        if kp_id is None:
            continue

        # 检查是否已存在（避免重复导入）
        existing = db.query(Question).filter(
            Question.knowledge_point_id == kp_id,
            Question.content == exam["content"],
        ).first()
        if existing:
            continue

        q = Question(
            knowledge_point_id=kp_id,
            question_type=exam["question_type"],
            content=exam["content"],
            answer=exam["answer"],
            explanation=exam["explanation"],
            difficulty=exam["difficulty"],
            source="past_exam",
            exam_year=exam["year"],
            exam_point=exam["exam_point"],
        )

        # 单选题校验：确保 answer 与 is_correct 的 label 一致
        if exam["question_type"] == "single_choice":
            correct_label = next(
                (label for label, _, ic in exam["options"] if ic), None
            )
            if correct_label and exam["answer"] != correct_label:
                q.answer = correct_label  # 自动修正 answer 字段

        db.add(q)
        db.flush()

        for label, content, is_correct in exam["options"]:
            db.add(QuestionOption(
                question_id=q.id,
                label=label,
                content=content,
                is_correct=is_correct,
            ))

        count += 1

    return count

