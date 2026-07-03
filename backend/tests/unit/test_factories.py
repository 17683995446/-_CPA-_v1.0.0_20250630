"""
测试数据工厂验证。

验证规范：
- 每个工厂函数正确创建 ORM 实例
- 工厂函数的默认值合理
- make_full_setup 正确创建完整数据集
- 工厂函数支持 kwargs 覆盖
"""
import pytest

from tests.factories import (
    make_full_setup,
    make_kp,
    make_mastery,
    make_question,
    make_question_with_options,
    make_review_card,
    make_study_session,
    make_user,
    make_user_profile,
)
from tests.shared_fixtures import isolated_db


class TestFactories:
    """工厂函数基础验证。"""

    def test_make_user(self, isolated_db):
        user = make_user(isolated_db, username="factory_user")
        isolated_db.commit()
        assert user.id is not None
        assert user.username == "factory_user"

    def test_make_user_with_custom_email(self, isolated_db):
        user = make_user(isolated_db, email="custom@test.com")
        assert user.email == "custom@test.com"

    def test_make_kp(self, isolated_db):
        kp = make_kp(isolated_db, code="AUD-01-01", name="审计目标")
        isolated_db.commit()
        assert kp.id is not None
        assert kp.code == "AUD-01-01"

    def test_make_question(self, isolated_db):
        kp = make_kp(isolated_db)
        q = make_question(isolated_db, knowledge_point_id=kp.id, content="工厂题目")
        isolated_db.commit()
        assert q.id is not None
        assert q.content == "工厂题目"

    def test_make_question_with_options(self, isolated_db):
        kp = make_kp(isolated_db)
        q, opts = make_question_with_options(
            isolated_db,
            content="1+1=?",
            correct_answer="2",
            wrong_answers=["0", "3", "4"],
            knowledge_point_id=kp.id,
        )
        isolated_db.commit()
        assert q.id is not None
        assert len(opts) == 4  # 1 correct + 3 wrong
        correct = [o for o in opts if o.is_correct]
        assert len(correct) == 1
        assert correct[0].content == "2"

    def test_make_mastery(self, isolated_db):
        user = make_user(isolated_db)
        kp = make_kp(isolated_db)
        m = make_mastery(isolated_db, user_id=user.id, knowledge_point_id=kp.id, p_known=0.5)
        isolated_db.commit()
        assert m.id is not None
        assert m.p_known == 0.5

    def test_make_review_card(self, isolated_db):
        user = make_user(isolated_db)
        kp = make_kp(isolated_db)
        q = make_question(isolated_db, knowledge_point_id=kp.id)
        card = make_review_card(isolated_db, user_id=user.id, question_id=q.id, knowledge_point_id=kp.id)
        isolated_db.commit()
        assert card.id is not None
        assert card.stability == 1.0

    def test_make_user_profile(self, isolated_db):
        user = make_user(isolated_db)
        profile = make_user_profile(isolated_db, user_id=user.id)
        isolated_db.commit()
        assert profile.id is not None
        assert profile.user_id == user.id

    def test_make_study_session(self, isolated_db):
        user = make_user(isolated_db)
        session = make_study_session(
            isolated_db, user_id=user.id,
            subject="会计",
            questions_answered=20, correct_count=15,
        )
        isolated_db.commit()
        assert session.id is not None
        assert session.questions_answered == 20


class TestFullSetup:
    """make_full_setup 完整数据集验证。"""

    def test_creates_all_entities(self, isolated_db):
        data = make_full_setup(isolated_db, question_count=3)
        isolated_db.commit()

        assert data["user"].id is not None
        assert data["kp"].id is not None
        assert data["profile"].id is not None
        assert data["mastery"].id is not None
        assert len(data["questions"]) == 3

    def test_questions_have_correct_options(self, isolated_db):
        data = make_full_setup(isolated_db, question_count=2)
        isolated_db.commit()

        for q, opts in data["questions"]:
            assert len(opts) == 4  # 1 correct + 3 wrong
            correct = [o for o in opts if o.is_correct]
            assert len(correct) == 1

    def test_mastery_links_user_and_kp(self, isolated_db):
        data = make_full_setup(isolated_db, question_count=1)
        isolated_db.commit()

        assert data["mastery"].user_id == data["user"].id
        assert data["mastery"].knowledge_point_id == data["kp"].id

    def test_questions_link_to_kp(self, isolated_db):
        data = make_full_setup(isolated_db, question_count=3)
        isolated_db.commit()

        for q, _ in data["questions"]:
            assert q.knowledge_point_id == data["kp"].id

    def test_zero_questions(self, isolated_db):
        data = make_full_setup(isolated_db, with_questions=False)
        isolated_db.commit()
        assert len(data["questions"]) == 0
        assert data["user"].id is not None
