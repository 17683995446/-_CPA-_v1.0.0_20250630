"""
Repository 数据访问层单元测试。

验证规范：
- BaseRepository CRUD 操作正确
- UserRepository 特定查询方法
- QuestionRepository 特定查询方法
- get_or_404 抛出 HTTPException
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.repository import BaseRepository
from app.db.repositories import (
    KnowledgePointRepository,
    MasteryRepository,
    QuestionRepository,
    UserRepository,
)
from app.models import KnowledgePoint, Question, User, UserMastery


@pytest.fixture
def db_session():
    """独立内存 SQLite 会话。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_kp(db, code="ACC-01-01", name="借贷记账法", subject="会计", chapter="第一章"):
    """创建知识点辅助函数。"""
    kp = KnowledgePoint(code=code, name=name, subject=subject, chapter=chapter)
    db.add(kp)
    db.flush()
    return kp


def _make_user(db=None, email="test@test.com", username="testuser", password_hash="h"):
    """创建用户辅助函数。"""
    user = User(username=username, email=email, password_hash=password_hash)
    if db:
        db.add(user)
        db.flush()
    return user


class TestBaseRepository:
    """BaseRepository 通用 CRUD 验证。"""

    def test_create_and_get_by_id(self, db_session):
        repo = UserRepository(db_session)
        user = repo.create(username="user1", email="test@example.com", password_hash="hash123")
        db_session.commit()
        assert user.id is not None
        found = repo.get_by_id(user.id)
        assert found is not None
        assert found.email == "test@example.com"

    def test_get_by_id_returns_none_when_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_by_id(99999) is None

    def test_get_or_404_raises_when_not_found(self, db_session):
        repo = UserRepository(db_session)
        with pytest.raises(HTTPException) as exc:
            repo.get_or_404(99999)
        assert exc.value.status_code == 404

    def test_get_all_with_pagination(self, db_session):
        repo = UserRepository(db_session)
        for i in range(5):
            repo.create(username=f"user{i}", email=f"user{i}@test.com", password_hash="hash")
        db_session.commit()
        all_users = repo.get_all(skip=0, limit=100)
        assert len(all_users) == 5
        first_two = repo.get_all(skip=0, limit=2)
        assert len(first_two) == 2

    def test_count(self, db_session):
        repo = UserRepository(db_session)
        assert repo.count() == 0
        repo.create(username="countuser", email="a@test.com", password_hash="h")
        db_session.commit()
        assert repo.count() == 1

    def test_delete(self, db_session):
        repo = UserRepository(db_session)
        user = repo.create(username="deluser", email="del@test.com", password_hash="h")
        db_session.commit()
        repo.delete(user)
        db_session.commit()
        assert repo.get_by_id(user.id) is None


class TestUserRepository:
    """UserRepository 特定查询验证。"""

    def test_find_by_email(self, db_session):
        repo = UserRepository(db_session)
        repo.create(username="findme", email="findme@test.com", password_hash="h")
        db_session.commit()
        user = repo.find_by_email("findme@test.com")
        assert user is not None
        assert user.email == "findme@test.com"

    def test_find_by_email_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.find_by_email("nonexistent@test.com") is None


class TestQuestionRepository:
    """QuestionRepository 特定查询验证。"""

    def test_get_by_kp(self, db_session):
        kp = _make_kp(db_session)
        repo = QuestionRepository(db_session)
        for i in range(3):
            db_session.add(Question(
                content=f"测试题{i}",
                question_type="single_choice",
                answer="A",
                explanation="解析",
                knowledge_point_id=kp.id,
            ))
        db_session.commit()

        results = repo.get_by_kp(kp.id, limit=10)
        assert len(results) == 3

    def test_count_all(self, db_session):
        kp = _make_kp(db_session)
        repo = QuestionRepository(db_session)
        for i in range(5):
            db_session.add(Question(
                content=f"题{i}",
                question_type="single_choice",
                answer="A",
                explanation="解析",
                knowledge_point_id=kp.id,
            ))
        db_session.commit()
        assert repo.count_all() == 5


class TestMasteryRepository:
    """MasteryRepository 特定查询验证。"""

    def test_get_or_create_creates_new(self, db_session):
        user = _make_user(db_session, email="m1@test.com", username="m1user")
        kp = _make_kp(db_session)

        repo = MasteryRepository(db_session)
        mastery = repo.get_or_create(user.id, kp.id)
        db_session.commit()
        assert mastery.id is not None
        assert mastery.user_id == user.id
        assert mastery.knowledge_point_id == kp.id

    def test_get_or_create_returns_existing(self, db_session):
        user = _make_user(db_session, email="m2@test.com", username="m2user")
        kp = _make_kp(db_session)

        repo = MasteryRepository(db_session)
        m1 = repo.get_or_create(user.id, kp.id)
        db_session.commit()
        m2 = repo.get_or_create(user.id, kp.id)
        assert m1.id == m2.id


class TestKnowledgePointRepository:
    """KnowledgePointRepository 特定查询验证。"""

    def test_get_by_code(self, db_session):
        _make_kp(db_session, code="ACC-03-01", name="存货初始计量")
        repo = KnowledgePointRepository(db_session)
        kp = repo.get_by_code("ACC-03-01")
        assert kp is not None
        assert kp.name == "存货初始计量"

    def test_get_by_subject(self, db_session):
        _make_kp(db_session, code="ACC-01-01", name="借贷记账法", subject="会计")
        _make_kp(db_session, code="AUD-01-01", name="审计目标", subject="审计")
        db_session.commit()
        repo = KnowledgePointRepository(db_session)
        accounting_kps = repo.get_by_subject("会计")
        assert len(accounting_kps) == 1
        assert accounting_kps[0].code == "ACC-01-01"
