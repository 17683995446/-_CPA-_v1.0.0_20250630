"""
测试数据工厂。

提供工厂函数生成测试所需的 ORM 模型实例，减少测试中的重复样板代码。

设计原理：
- 工厂函数返回未提交的 ORM 实例，调用方决定是否 commit
- 每个工厂提供合理的默认值，可通过 kwargs 覆盖
- 关联实体通过嵌套工厂自动创建
"""
from __future__ import annotations

from app.models import (
    Achievement,
    KnowledgePoint,
    Question,
    QuestionOption,
    ReviewCard,
    StudySession,
    User,
    UserAchievement,
    UserMastery,
    UserProfile,
    UserStreak,
)


def make_user(
    db=None,
    username="testuser",
    email="test@test.com",
    password_hash="$2b$12$dummyhash",
) -> User:
    """创建用户。"""
    user = User(username=username, email=email, password_hash=password_hash)
    if db:
        db.add(user)
        db.flush()
    return user


def make_kp(
    db=None,
    code="ACC-01-01",
    name="借贷记账法",
    subject="会计",
    chapter="第一章",
    description="测试知识点",
) -> KnowledgePoint:
    """创建知识点。"""
    kp = KnowledgePoint(
        code=code, name=name, subject=subject,
        chapter=chapter, description=description,
    )
    if db:
        db.add(kp)
        db.flush()
    return kp


def make_question(
    db=None,
    content="测试题目内容",
    question_type="single_choice",
    answer="A",
    explanation="测试解析",
    knowledge_point_id=None,
    difficulty=3,
) -> Question:
    """创建题目（不含选项）。"""
    q = Question(
        content=content,
        question_type=question_type,
        answer=answer,
        explanation=explanation,
        knowledge_point_id=knowledge_point_id,
        difficulty=difficulty,
    )
    if db:
        db.add(q)
        db.flush()
    return q


def make_question_with_options(
    db=None,
    content="2+3等于多少？",
    correct_answer="5",
    wrong_answers=None,
    knowledge_point_id=None,
) -> tuple[Question, list[QuestionOption]]:
    """创建题目及其选项。"""
    if wrong_answers is None:
        wrong_answers = ["4", "6", "7"]
    q = make_question(db=db, content=content, knowledge_point_id=knowledge_point_id)
    options = []
    # 正确选项
    options.append(QuestionOption(
        question_id=q.id, label="A", content=correct_answer, is_correct=True,
    ))
    # 错误选项
    for i, wrong in enumerate(wrong_answers[:3]):
        options.append(QuestionOption(
            question_id=q.id, label=chr(66 + i), content=wrong, is_correct=False,
        ))
    if db:
        db.add_all(options)
        db.flush()
    return q, options


def make_mastery(
    db=None,
    user_id=None,
    knowledge_point_id=None,
    p_known=0.1,
    total_answers=0,
    correct_answers=0,
) -> UserMastery:
    """创建掌握度记录。"""
    mastery = UserMastery(
        user_id=user_id,
        knowledge_point_id=knowledge_point_id,
        p_known=p_known,
        total_answers=total_answers,
        correct_answers=correct_answers,
    )
    if db:
        db.add(mastery)
        db.flush()
    return mastery


def make_review_card(
    db=None,
    user_id=None,
    question_id=None,
    knowledge_point_id=None,
    stability=1.0,
    difficulty=5.0,
    due=None,
    state=0,
    reps=0,
) -> ReviewCard:
    """创建复习卡片。"""
    from datetime import date
    if due is None:
        due = date(2026, 7, 2)
    elif isinstance(due, str):
        from datetime import datetime
        due = datetime.strptime(due, "%Y-%m-%d").date()
    card = ReviewCard(
        user_id=user_id,
        question_id=question_id,
        knowledge_point_id=knowledge_point_id,
        stability=stability,
        difficulty=difficulty,
        due=due,
        state=state,
        reps=reps,
    )
    if db:
        db.add(card)
        db.flush()
    return card


def make_user_profile(
    db=None,
    user_id=None,
    target_exam_date=None,
    daily_goal_minutes=120,
) -> UserProfile:
    """创建用户画像。"""
    from datetime import date
    if target_exam_date is None:
        target_exam_date = date(2026, 10, 1)
    elif isinstance(target_exam_date, str):
        from datetime import datetime
        target_exam_date = datetime.strptime(target_exam_date, "%Y-%m-%d").date()
    profile = UserProfile(
        user_id=user_id,
        target_exam_date=target_exam_date,
        daily_goal_minutes=daily_goal_minutes,
    )
    if db:
        db.add(profile)
        db.flush()
    return profile


def make_study_session(
    db=None,
    user_id=None,
    subject="会计",
    questions_answered=10,
    correct_count=7,
) -> StudySession:
    """创建学习会话。"""
    from datetime import datetime
    session = StudySession(
        user_id=user_id,
        subject=subject,
        started_at=datetime.now(),
        questions_answered=questions_answered,
        correct_count=correct_count,
    )
    if db:
        db.add(session)
        db.flush()
    return session


def make_full_setup(db, with_questions=True, question_count=5):
    """一键创建完整的测试数据集（用户+知识点+题目+掌握度）。

    返回 dict 包含所有创建的实体引用。
    """
    user = make_user(db, username="fulluser", email="full@test.com")
    kp = make_kp(db)
    profile = make_user_profile(db, user_id=user.id)

    questions = []
    if with_questions:
        for i in range(question_count):
            q, opts = make_question_with_options(
                db,
                content=f"测试题{i+1}",
                correct_answer=f"答案{i+1}",
                wrong_answers=[f"错{i+1}a", f"错{i+1}b", f"错{i+1}c"],
                knowledge_point_id=kp.id,
            )
            questions.append((q, opts))

    mastery = make_mastery(db, user_id=user.id, knowledge_point_id=kp.id)
    db.flush()

    return {
        "user": user,
        "kp": kp,
        "profile": profile,
        "questions": questions,
        "mastery": mastery,
    }
