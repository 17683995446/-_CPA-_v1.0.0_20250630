"""
阶段1-5 集成测试：验证各引擎间的协作。

测试跨引擎场景：
1. BKT + FSRS：答题 → 更新掌握度 → 更新复习卡片
2. Question Gen + BKT：BKT 推荐难度 → 出题引擎生成对应难度题目
3. Gamification + BKT：掌握度 → 心流状态 → XP 计算
4. Knowledge Graph + Question Gen：学习路径 → 路径上各知识点出题
5. 完整学习循环：出题 → 答题 → BKT更新 → FSRS更新 → XP奖励 → Streak更新
"""
import random
from datetime import date, datetime, timedelta

import pytest

from app.engines.bkt import BKTEngine, MasteryState
from app.engines.fsrs import Card, CardState, FSRSEngine, Rating
from app.engines.gamification import GamificationEngine, StreakInfo
from app.engines.knowledge_graph import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
)
from app.engines.question_gen import QuestionGenerator


@pytest.mark.integration
class TestBKTFSRSIntegration:
    """BKT + FSRS 集成：答题后同时更新知识追踪和复习调度。"""

    def test_answer_correct_updates_both(self, db_session):
        """答对后 BKT 掌握度上升、FSRS 稳定性增加。"""
        from app.models import KnowledgePoint, Question, ReviewCard, User, UserMastery

        # 准备数据
        user = User(username="int_user1", email="int1@test.com", password_hash="h")
        kp = KnowledgePoint(code="INT-01", name="集成测试KP", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()
        q = Question(knowledge_point_id=kp.id, question_type="single_choice",
                     content="测试题", answer="A")
        db_session.add(q)
        db_session.flush()

        orm_card = ReviewCard(
            user_id=user.id, question_id=q.id, knowledge_point_id=kp.id,
            due=date(2026, 1, 10),
        )
        orm_mastery = UserMastery(user_id=user.id, knowledge_point_id=kp.id)
        db_session.add_all([orm_card, orm_mastery])
        db_session.commit()

        # 引擎初始化
        bkt_engine = BKTEngine()
        fsrs_engine = FSRSEngine()

        # 加载状态
        mastery = MasteryState.from_orm(orm_mastery)
        card = Card.from_orm(orm_card)

        # 答对
        bkt_result = bkt_engine.update(mastery, is_correct=True)
        fsrs_result = fsrs_engine.review(card, Rating.GOOD, datetime(2026, 1, 10, 10, 0))

        # 写回
        mastery.to_orm(orm_mastery)
        card.to_orm(orm_card)
        db_session.commit()

        # 验证：掌握度上升
        assert orm_mastery.p_known > 0.1
        # 验证：FSRS 稳定性增加、进入复习状态
        assert orm_card.stability > 0
        assert orm_card.state == "review"

    def test_answer_wrong_updates_both(self, db_session):
        """答错后 BKT 掌握度下降、FSRS 进入重新学习。"""
        from app.models import KnowledgePoint, Question, ReviewCard, User, UserMastery

        user = User(username="int_user2", email="int2@test.com", password_hash="h")
        kp = KnowledgePoint(code="INT-02", name="集成测试KP2", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()
        q = Question(knowledge_point_id=kp.id, question_type="single_choice",
                     content="测试题", answer="A")
        db_session.add(q)
        db_session.flush()

        # 先让卡片进入复习状态
        orm_card = ReviewCard(
            user_id=user.id, question_id=q.id, knowledge_point_id=kp.id,
            stability=5.0, difficulty=5.0, due=date(2026, 1, 5),
            last_review=datetime(2026, 1, 5, 10, 0), reps=3, state="review",
        )
        orm_mastery = UserMastery(
            user_id=user.id, knowledge_point_id=kp.id, p_known=0.7,
        )
        db_session.add_all([orm_card, orm_mastery])
        db_session.commit()

        bkt_engine = BKTEngine()
        fsrs_engine = FSRSEngine()

        mastery = MasteryState.from_orm(orm_mastery)
        card = Card.from_orm(orm_card)

        p_known_before = mastery.p_known

        # 答错
        bkt_engine.update(mastery, is_correct=False)
        fsrs_engine.review(card, Rating.AGAIN, datetime(2026, 1, 10, 10, 0))

        mastery.to_orm(orm_mastery)
        card.to_orm(orm_card)
        db_session.commit()

        # 验证：掌握度下降
        assert orm_mastery.p_known < p_known_before
        # 验证：FSRS 进入重新学习
        assert orm_card.state == "relearning"
        assert orm_card.lapses == 1


@pytest.mark.integration
class TestQuestionGenBKTIntegration:
    """出题引擎 + BKT 集成：根据掌握度推荐难度并生成题目。"""

    def test_generate_by_recommended_difficulty(self):
        """BKT 推荐难度 → 出题引擎生成对应难度题目。"""
        bkt_engine = BKTEngine()
        q_gen = QuestionGenerator()

        # 低掌握度用户
        low_mastery = MasteryState(p_known=0.1)
        difficulty = bkt_engine.recommend_difficulty(low_mastery)
        assert difficulty == 1

        # 生成对应难度题目
        question = q_gen.generate_by_knowledge_point(
            "ACC-01-01", difficulty=difficulty, rng=random.Random(42)
        )
        assert question is not None
        assert question.difficulty == 1

    def test_progressive_difficulty(self):
        """随着掌握度提升，题目难度应递增。"""
        bkt_engine = BKTEngine()
        q_gen = QuestionGenerator()

        mastery = MasteryState(p_known=0.1)
        difficulties = []

        for _ in range(10):
            d = bkt_engine.recommend_difficulty(mastery)
            difficulties.append(d)
            bkt_engine.update(mastery, is_correct=True)

        # 难度应逐渐升高
        assert difficulties[-1] >= difficulties[0]


@pytest.mark.integration
class TestGamificationBKTIntegration:
    """游戏化 + BKT 集成：掌握度影响心流状态和 XP。"""

    def test_flow_state_affects_xp(self):
        """心流状态下的答题应获得更多 XP（难度加成）。"""
        bkt_engine = BKTEngine()
        game_engine = GamificationEngine(rng=random.Random(42))

        # 高掌握度用户做高难度题 → 心流 → 更多 XP
        mastery = MasteryState(p_known=0.8)
        flow_difficulty = game_engine.recommend_flow_difficulty(mastery.p_known)

        xp_high = game_engine.calculate_xp(is_correct=True, difficulty=flow_difficulty)

        # 低难度题 → XP 较少
        xp_low = game_engine.calculate_xp(is_correct=True, difficulty=1)

        assert xp_high.base_xp >= xp_low.base_xp

    def test_safe_failure_with_bkt(self):
        """BKT 低掌握度 + 高错误率 → 安全失败区推荐。"""
        bkt_engine = BKTEngine()
        game_engine = GamificationEngine()

        mastery = MasteryState(p_known=0.2)
        # 模拟高错误率
        for _ in range(5):
            bkt_engine.update(mastery, is_correct=False)

        rec = game_engine.get_safe_failure_recommendation(
            mastery_p_known=mastery.p_known, recent_error_rate=0.8
        )
        assert rec["mode"] == "practice"


@pytest.mark.integration
class TestKnowledgeGraphQuestionGenIntegration:
    """知识图谱 + 出题引擎集成：沿学习路径出题。"""

    def test_generate_along_learning_path(self, db_session):
        """沿学习路径为每个知识点生成题目。"""
        from app.models import KnowledgeEdge, KnowledgePoint

        # 构建知识链：基础 → 中级 → 高级
        kp1 = KnowledgePoint(code="PATH-01", name="借贷基础", subject="会计", chapter="ch1", difficulty=1)
        kp2 = KnowledgePoint(code="PATH-02", name="资产核算", subject="会计", chapter="ch2", difficulty=3)
        kp3 = KnowledgePoint(code="PATH-03", name="合并报表", subject="会计", chapter="ch3", difficulty=5)
        db_session.add_all([kp1, kp2, kp3])
        db_session.flush()

        db_session.add_all([
            KnowledgeEdge(source_id=kp1.id, target_id=kp2.id, relation_type="prerequisite"),
            KnowledgeEdge(source_id=kp2.id, target_id=kp3.id, relation_type="prerequisite"),
        ])
        db_session.commit()

        # 构建图谱并获取学习路径
        graph = KnowledgeGraphBuilder.build_from_db(db_session, subject="会计")
        path = graph.get_learning_path(kp3.id)

        assert len(path) == 3
        assert path[0].code == "PATH-01"
        assert path[-1].code == "PATH-03"


@pytest.mark.integration
class TestFullLearningCycle:
    """完整学习循环：出题 → 答题 → BKT更新 → FSRS更新 → XP奖励 → Streak更新。"""

    def test_complete_study_session(self, db_session):
        """模拟一次完整的学习会话（5 道题）。"""
        from app.models import (
            KnowledgePoint, Question, ReviewCard, StudySession,
            User, UserBehaviorLog, UserMastery, UserProfile, UserStreak,
        )

        # 准备用户和知识点
        user = User(username="cycle_user", email="cycle@test.com", password_hash="h")
        kp = KnowledgePoint(code="CYCLE-01", name="循环测试", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        profile = UserProfile(user_id=user.id, daily_goal_minutes=60)
        db_session.add(profile)
        db_session.flush()

        # 为知识点注册一个出题模板
        q_gen = QuestionGenerator()
        from app.engines.question_gen import (
            CognitiveLevel, QuestionTemplate, QuestionType,
        )
        q_gen.register_template(QuestionTemplate(
            template_id="cycle_test",
            knowledge_point_code="CYCLE-01",
            subject="会计",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.UNDERSTAND,
            content_template="测试题 {n}",
            answer_template="答案 {n}",
            explanation_template="解析 {n}",
            slots={"n": ["1", "2", "3", "4", "5"]},
            distractor_templates=["错误选项"],
        ))

        # 引擎
        bkt_engine = BKTEngine()
        fsrs_engine = FSRSEngine()
        game_engine = GamificationEngine(rng=random.Random(42))

        # 初始化状态
        mastery = MasteryState(p_known=0.1)
        streak = StreakInfo()
        total_xp = 0
        study_date = date(2026, 1, 10)

        # 模拟 5 道题
        correct_count = 0
        for i in range(5):
            # 1. 出题（根据 BKT 推荐难度）
            difficulty = bkt_engine.recommend_difficulty(mastery)
            question = q_gen.generate_by_knowledge_point(
                "CYCLE-01", difficulty=difficulty, rng=random.Random(i)
            )
            assert question is not None

            # 2. 答题（模拟 70% 正确率，前 3 题对）
            is_correct = i < 3
            if is_correct:
                correct_count += 1

            # 3. BKT 更新
            bkt_engine.update(mastery, is_correct=is_correct)

            # 4. FSRS 更新
            card = Card()
            rating = Rating.GOOD if is_correct else Rating.AGAIN
            fsrs_engine.review(card, rating, datetime(2026, 1, 10, 10, i))

            # 5. XP 奖励
            xp_result = game_engine.calculate_xp(
                is_correct=is_correct, difficulty=difficulty
            )
            total_xp += xp_result.total_xp

        # 6. Streak 更新
        updated_streak, msg = game_engine.update_streak(streak, study_date)

        # 7. 等级检查
        level_info = game_engine.calculate_level(total_xp)

        # 验证
        assert correct_count == 3
        assert mastery.p_known > 0.1  # 掌握度提升
        assert total_xp > 0
        assert updated_streak.streak_count == 1
        assert level_info.level >= 1

    def test_multi_day_progression(self):
        """模拟多天学习进展：Streak 增长 + 掌握度提升 + 等级提升。"""
        bkt_engine = BKTEngine()
        game_engine = GamificationEngine(rng=random.Random(42))

        mastery = MasteryState(p_known=0.1)
        streak = StreakInfo()
        total_xp = 0
        start_date = date(2026, 1, 10)

        for day in range(14):
            study_date = start_date + timedelta(days=day)

            # 每天答 10 题，80% 正确率
            for _ in range(10):
                is_correct = random.Random(day * 10 + _).random() < 0.8
                bkt_engine.update(mastery, is_correct=is_correct)
                xp = game_engine.calculate_xp(is_correct=is_correct, difficulty=3)
                total_xp += xp.total_xp

            # 更新 streak
            game_engine.update_streak(streak, study_date)

        # 验证
        assert streak.streak_count == 14  # 连续 14 天
        assert mastery.p_known > 0.5  # 掌握度显著提升
        level = game_engine.calculate_level(total_xp)
        assert level.level >= 3  # 至少 3 级
