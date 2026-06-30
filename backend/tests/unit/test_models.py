"""
阶段1 单元测试：数据模型与数据库基础。

测试范围：
- 所有 ORM 模型的字段定义和默认值
- 模型间的外键关系和级联删除
- 唯一约束
- 配置正确性
"""
import pytest
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import (
    Achievement,
    KnowledgeEdge,
    KnowledgePoint,
    Question,
    QuestionOption,
    ReviewCard,
    ReviewLog,
    StudySession,
    User,
    UserAchievement,
    UserBehaviorLog,
    UserMastery,
    UserProfile,
    UserStreak,
)


@pytest.mark.unit
class TestConfig:
    """测试应用配置。"""

    def test_cpa_subjects_count(self):
        """CPA 考试应有 6 个科目。"""
        assert len(settings.CPA_SUBJECTS) == 6

    def test_cpa_subjects_content(self):
        """科目名称应符合注册会计师考试规范。"""
        expected = {"会计", "审计", "财务成本管理", "公司战略与风险管理", "经济法", "税法"}
        assert set(settings.CPA_SUBJECTS) == expected

    def test_fsrs_defaults(self):
        """FSRS 默认参数应在合理范围。"""
        assert 0 < settings.FSRS_REQUEST_RETENTION < 1
        assert settings.FSRS_MAXIMUM_INTERVAL > 0

    def test_bkt_defaults(self):
        """BKT 默认参数应在概率范围内。"""
        assert 0 < settings.BKT_DEFAULT_P_INIT < 1
        assert 0 < settings.BKT_DEFAULT_P_TRANSIT < 1
        assert 0 < settings.BKT_DEFAULT_P_GUESS < 0.5  # guess 应小于 0.5
        assert 0 < settings.BKT_DEFAULT_P_SLIP < 0.5   # slip 应小于 0.5


@pytest.mark.unit
class TestUserModel:
    """测试用户模型。"""

    def test_create_user(self, db_session):
        """创建用户应成功并生成 id 和时间戳。"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_username_unique(self, db_session):
        """用户名应唯一。"""
        user1 = User(username="dup", email="a@test.com", password_hash="h")
        db_session.add(user1)
        db_session.commit()

        user2 = User(username="dup", email="b@test.com", password_hash="h")
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_email_unique(self, db_session):
        """邮箱应唯一。"""
        user1 = User(username="u1", email="same@test.com", password_hash="h")
        db_session.add(user1)
        db_session.commit()

        user2 = User(username="u2", email="same@test.com", password_hash="h")
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_user_profile_relationship(self, db_session):
        """用户与画像应为一对一关系。"""
        user = User(username="puser", email="p@test.com", password_hash="h")
        db_session.add(user)
        db_session.flush()

        profile = UserProfile(
            user_id=user.id,
            target_exam_date=date(2026, 8, 28),
            daily_goal_minutes=90,
        )
        db_session.add(profile)
        db_session.commit()

        assert user.profile is not None
        assert user.profile.daily_goal_minutes == 90
        assert user.profile.current_level == 1
        assert user.profile.total_xp == 0

    def test_cascade_delete_user(self, db_session):
        """删除用户应级联删除画像。"""
        user = User(username="deluser", email="del@test.com", password_hash="h")
        db_session.add(user)
        db_session.flush()

        profile = UserProfile(user_id=user.id)
        db_session.add(profile)
        db_session.commit()
        profile_id = profile.id

        db_session.delete(user)
        db_session.commit()

        assert db_session.get(UserProfile, profile_id) is None


@pytest.mark.unit
class TestKnowledgeModel:
    """测试知识点模型。"""

    def test_create_knowledge_point(self, db_session):
        """创建知识点应成功。"""
        kp = KnowledgePoint(
            code="ACC-01-01",
            name="借贷记账法",
            subject="会计",
            chapter="总论",
            difficulty=3,
        )
        db_session.add(kp)
        db_session.commit()

        assert kp.id is not None
        assert kp.mastery_default == 0.1
        assert kp.difficulty == 3

    def test_code_unique(self, db_session):
        """知识点编码应唯一。"""
        kp1 = KnowledgePoint(
            code="DUP-01", name="A", subject="会计", chapter="ch1"
        )
        db_session.add(kp1)
        db_session.commit()

        kp2 = KnowledgePoint(
            code="DUP-01", name="B", subject="会计", chapter="ch2"
        )
        db_session.add(kp2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_knowledge_edge(self, db_session):
        """知识点间应能建立前置依赖关系。"""
        kp1 = KnowledgePoint(code="E-01", name="基础", subject="会计", chapter="ch1")
        kp2 = KnowledgePoint(code="E-02", name="进阶", subject="会计", chapter="ch2")
        db_session.add_all([kp1, kp2])
        db_session.flush()

        edge = KnowledgeEdge(
            source_id=kp1.id, target_id=kp2.id, relation_type="prerequisite"
        )
        db_session.add(edge)
        db_session.commit()

        assert edge.id is not None
        assert edge.relation_type == "prerequisite"


@pytest.mark.unit
class TestQuestionModel:
    """测试题目模型。"""

    def _create_kp(self, db_session, code="Q-01"):
        kp = KnowledgePoint(code=code, name="测试知识点", subject="会计", chapter="ch1")
        db_session.add(kp)
        db_session.flush()
        return kp

    def test_create_question(self, db_session):
        """创建题目应成功。"""
        kp = self._create_kp(db_session)
        q = Question(
            knowledge_point_id=kp.id,
            question_type="single_choice",
            content="下列哪项是资产？",
            answer="A",
            difficulty=2,
            source="past_exam",
        )
        db_session.add(q)
        db_session.commit()

        assert q.id is not None
        assert q.source == "past_exam"
        assert q.knowledge_point is not None

    def test_question_options(self, db_session):
        """题目应能关联多个选项。"""
        kp = self._create_kp(db_session, code="Q-02")
        q = Question(
            knowledge_point_id=kp.id,
            question_type="single_choice",
            content="题干",
            answer="B",
        )
        db_session.add(q)
        db_session.flush()

        opt_a = QuestionOption(question_id=q.id, label="A", content="选项A", is_correct=False)
        opt_b = QuestionOption(question_id=q.id, label="B", content="选项B", is_correct=True)
        db_session.add_all([opt_a, opt_b])
        db_session.commit()

        assert len(q.options) == 2
        correct = [o for o in q.options if o.is_correct]
        assert len(correct) == 1
        assert correct[0].label == "B"


@pytest.mark.unit
class TestReviewModel:
    """测试复习卡片模型。"""

    def _create_prerequisites(self, db_session, code_prefix="R"):
        user = User(username=f"{code_prefix}_user", email=f"{code_prefix}@test.com", password_hash="h")
        kp = KnowledgePoint(code=f"{code_prefix}-kp", name="kp", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()
        q = Question(knowledge_point_id=kp.id, question_type="single_choice", content="c", answer="A")
        db_session.add(q)
        db_session.flush()
        return user, kp, q

    def test_create_review_card(self, db_session):
        """创建复习卡片应有正确的 FSRS 默认值。"""
        user, kp, q = self._create_prerequisites(db_session)
        card = ReviewCard(
            user_id=user.id,
            question_id=q.id,
            knowledge_point_id=kp.id,
            due=date(2026, 1, 15),
        )
        db_session.add(card)
        db_session.commit()

        assert card.stability == 0.0
        assert card.difficulty == 0.0
        assert card.reps == 0
        assert card.lapses == 0
        assert card.state == "new"

    def test_review_log(self, db_session):
        """复习日志应记录评分和状态变化。"""
        user, kp, q = self._create_prerequisites(db_session, code_prefix="RL")
        card = ReviewCard(
            user_id=user.id,
            question_id=q.id,
            knowledge_point_id=kp.id,
            due=date(2026, 1, 15),
        )
        db_session.add(card)
        db_session.flush()

        log = ReviewLog(
            card_id=card.id,
            user_id=user.id,
            rating=3,
            review_time=datetime(2026, 1, 10, 10, 0),
            elapsed_days=0.0,
            scheduled_days=1.0,
            state="learning",
            stability_before=0.0,
            difficulty_before=0.0,
            stability_after=1.5,
            difficulty_after=5.0,
        )
        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert len(card.logs) == 1
        assert card.logs[0].rating == 3


@pytest.mark.unit
class TestMasteryModel:
    """测试掌握度模型。"""

    def test_create_mastery(self, db_session):
        """创建掌握度记录应有 BKT 默认参数。"""
        user = User(username="m_user", email="m@test.com", password_hash="h")
        kp = KnowledgePoint(code="M-01", name="m", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        mastery = UserMastery(user_id=user.id, knowledge_point_id=kp.id)
        db_session.add(mastery)
        db_session.commit()

        assert mastery.p_known == 0.1
        assert mastery.p_transit == 0.3
        assert mastery.p_guess == 0.25
        assert mastery.p_slip == 0.1
        assert mastery.total_answers == 0
        assert mastery.correct_answers == 0

    def test_unique_user_kp(self, db_session):
        """同一用户对同一知识点只能有一条掌握度记录。"""
        user = User(username="m2_user", email="m2@test.com", password_hash="h")
        kp = KnowledgePoint(code="M-02", name="m2", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        m1 = UserMastery(user_id=user.id, knowledge_point_id=kp.id)
        db_session.add(m1)
        db_session.commit()

        m2 = UserMastery(user_id=user.id, knowledge_point_id=kp.id)
        db_session.add(m2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


@pytest.mark.unit
class TestGamificationModel:
    """测试游戏化模型。"""

    def test_create_achievement(self, db_session):
        """创建成就定义应成功。"""
        ach = Achievement(
            code="first_review",
            name="初次复习",
            description="完成第一次复习",
            category="learning",
            condition_type="questions_answered",
            condition_value=1,
            xp_reward=20,
        )
        db_session.add(ach)
        db_session.commit()

        assert ach.id is not None
        assert ach.xp_reward == 20

    def test_user_achievement(self, db_session):
        """用户成就关联应正确。"""
        user = User(username="g_user", email="g@test.com", password_hash="h")
        db_session.add(user)
        db_session.flush()

        ach = Achievement(
            code="streak_7",
            name="连续7天",
            description="连续学习7天",
            category="streak",
            condition_type="streak_days",
            condition_value=7,
        )
        db_session.add(ach)
        db_session.flush()

        ua = UserAchievement(user_id=user.id, achievement_id=ach.id)
        db_session.add(ua)
        db_session.commit()

        assert ua.id is not None

    def test_user_streak(self, db_session):
        """用户连续学习记录应有默认值。"""
        user = User(username="s_user", email="s@test.com", password_hash="h")
        db_session.add(user)
        db_session.flush()

        streak = UserStreak(user_id=user.id)
        db_session.add(streak)
        db_session.commit()

        assert streak.streak_count == 0
        assert streak.max_streak == 0
        assert streak.protections == 1
        assert streak.last_study_date is None


@pytest.mark.unit
class TestStudySessionModel:
    """测试学习会话模型。"""

    def test_create_session(self, db_session):
        """创建学习会话应成功。"""
        user = User(username="ss_user", email="ss@test.com", password_hash="h")
        db_session.add(user)
        db_session.flush()

        session = StudySession(
            user_id=user.id,
            subject="会计",
            started_at=datetime(2026, 1, 10, 9, 0),
            ended_at=datetime(2026, 1, 10, 10, 0),
            questions_answered=20,
            correct_count=15,
            xp_earned=150,
        )
        db_session.add(session)
        db_session.commit()

        assert session.id is not None
        assert session.questions_answered == 20
        assert session.correct_count == 15
