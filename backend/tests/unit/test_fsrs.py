"""
阶段2 单元测试：FSRS 间隔重复引擎。

测试范围：
- 遗忘曲线公式正确性
- 初始稳定性和难度
- 回忆/遗忘后的稳定性更新
- 难度更新与均值回归
- 间隔计算
- 卡片状态流转
- 完整复习流程
- ORM 模型互转
"""
import math
from datetime import date, datetime, timedelta

import pytest

from app.engines.fsrs import (
    DEFAULT_WEIGHTS,
    Card,
    CardState,
    FSRSEngine,
    Rating,
    ReviewResult,
)


@pytest.mark.unit
class TestRetrievability:
    """测试遗忘曲线（可提取性）公式。"""

    def setup_method(self):
        self.engine = FSRSEngine()

    def test_zero_elapsed_full_recall(self):
        """刚复习完（t=0），回忆概率应为 1.0。"""
        assert self.engine.retrievability(0, 10.0) == pytest.approx(1.0)

    def test_infinite_elapsed_zero_recall(self):
        """经过极长时间，回忆概率应趋近 0。"""
        assert self.engine.retrievability(100000, 10.0) < 0.01

    def test_higher_stability_slower_decay(self):
        """稳定性越高，相同时间后回忆概率越高。"""
        r_low_s = self.engine.retrievability(10, 1.0)
        r_high_s = self.engine.retrievability(10, 10.0)
        assert r_high_s > r_low_s

    def test_formula_exact(self):
        """验证公式 R = (1 + t/(9*S))^(-1) 的精确值。"""
        # t=9*S 时 R = (1+1)^(-1) = 0.5
        assert self.engine.retrievability(90, 10.0) == pytest.approx(0.5)
        # t=0 时 R = 1
        assert self.engine.retrievability(0, 5.0) == pytest.approx(1.0)

    def test_zero_stability_zero_recall(self):
        """稳定性为 0 时回忆概率应为 0。"""
        assert self.engine.retrievability(1, 0.0) == 0.0


@pytest.mark.unit
class TestNextInterval:
    """测试间隔计算。"""

    def setup_method(self):
        self.engine = FSRSEngine(request_retention=0.9)

    def test_interval_formula(self):
        """验证 interval = S * 9 * (1/0.9 - 1) = S * 1。"""
        # 1/0.9 - 1 = 0.111..., 9 * 0.111... = 1.0
        # 所以 interval ≈ S
        assert self.engine.next_interval(10.0) == pytest.approx(10, abs=1)

    def test_minimum_interval(self):
        """间隔最小为 1 天。"""
        assert self.engine.next_interval(0.01) == 1

    def test_maximum_interval(self):
        """间隔不超过最大值。"""
        engine = FSRSEngine(maximum_interval=100)
        assert engine.next_interval(100000.0) == 100

    def test_higher_retention_shorter_interval(self):
        """目标保持率越高，间隔越短。"""
        engine_90 = FSRSEngine(request_retention=0.9)
        engine_95 = FSRSEngine(request_retention=0.95)
        s = 10.0
        assert engine_95.next_interval(s) <= engine_90.next_interval(s)


@pytest.mark.unit
class TestInitialStability:
    """测试初始稳定性。"""

    def setup_method(self):
        self.engine = FSRSEngine()

    def test_again_lowest_stability(self):
        """Again 评分应有最低初始稳定性。"""
        s = self.engine._init_stability(Rating.AGAIN)
        assert s == DEFAULT_WEIGHTS[0]
        assert s == 0.4

    def test_easy_highest_stability(self):
        """Easy 评分应有最高初始稳定性。"""
        s = self.engine._init_stability(Rating.EASY)
        assert s == DEFAULT_WEIGHTS[3]
        assert s == 5.8

    def test_ordering(self):
        """初始稳定性应满足 Again < Hard < Good < Easy。"""
        values = [self.engine._init_stability(r) for r in Rating]
        assert values == sorted(values)


@pytest.mark.unit
class TestInitialDifficulty:
    """测试初始难度。"""

    def setup_method(self):
        self.engine = FSRSEngine()

    def test_good_rating_default_difficulty(self):
        """Good 评分（g=3）的初始难度应等于 w[4]。"""
        d = self.engine._init_difficulty(Rating.GOOD)
        assert d == pytest.approx(DEFAULT_WEIGHTS[4])

    def test_again_higher_difficulty(self):
        """Again 评分应有更高难度。"""
        d_again = self.engine._init_difficulty(Rating.AGAIN)
        d_good = self.engine._init_difficulty(Rating.GOOD)
        assert d_again > d_good

    def test_easy_lower_difficulty(self):
        """Easy 评分应有更低难度。"""
        d_easy = self.engine._init_difficulty(Rating.EASY)
        d_good = self.engine._init_difficulty(Rating.GOOD)
        assert d_easy < d_good

    def test_clamp_to_range(self):
        """难度应在 [1, 10] 范围内。"""
        for rating in Rating:
            d = self.engine._init_difficulty(rating)
            assert 1.0 <= d <= 10.0


@pytest.mark.unit
class TestDifficultyUpdate:
    """测试难度更新。"""

    def setup_method(self):
        self.engine = FSRSEngine()

    def test_again_increases_difficulty(self):
        """Again 评分应增加难度（从基准值开始，均值回归不会反向）。"""
        # 使用 w[4] 作为基准，确保均值回归不会反向拉低
        d_before = DEFAULT_WEIGHTS[4]  # 4.93
        d_after = self.engine._next_difficulty(d_before, Rating.AGAIN)
        assert d_after > d_before

    def test_easy_decreases_difficulty(self):
        """Easy 评分应降低难度（从基准值开始）。"""
        d_before = DEFAULT_WEIGHTS[4]  # 4.93
        d_after = self.engine._next_difficulty(d_before, Rating.EASY)
        assert d_after < d_before

    def test_clamp_to_range(self):
        """更新后难度应在 [1, 10] 范围内。"""
        for rating in Rating:
            d = self.engine._next_difficulty(9.9, rating)
            assert 1.0 <= d <= 10.0
            d = self.engine._next_difficulty(1.1, rating)
            assert 1.0 <= d <= 10.0

    def test_mean_reversion(self):
        """均值回归：难度应向 w[4] 方向偏移。"""
        # 从极端值开始
        d_extreme = 10.0
        d_after = self.engine._next_difficulty(d_extreme, Rating.GOOD)
        # Good 不改变 D'，但均值回归会拉回 w[4]
        # D' = 10 - w[6] * (3-3) = 10
        # D = w[7] * 10 + (1-w[7]) * w[4] = 0.01*10 + 0.99*4.93 ≈ 4.99
        assert d_after < d_extreme  # 被拉回


@pytest.mark.unit
class TestStabilityAfterRecall:
    """测试回忆成功后的稳定性更新。"""

    def setup_method(self):
        self.engine = FSRSEngine()

    def test_stability_increases_on_recall(self):
        """回忆成功后稳定性应增加。"""
        d, s, r = 5.0, 10.0, 0.9
        for rating in [Rating.HARD, Rating.GOOD, Rating.EASY]:
            s_new = self.engine._stability_after_recall(d, s, r, rating)
            assert s_new > s

    def test_easy_higher_than_good(self):
        """Easy 的稳定性增长应大于 Good。"""
        d, s, r = 5.0, 10.0, 0.9
        s_good = self.engine._stability_after_recall(d, s, r, Rating.GOOD)
        s_easy = self.engine._stability_after_recall(d, s, r, Rating.EASY)
        assert s_easy > s_good

    def test_hard_lower_than_good(self):
        """Hard 的稳定性增长应小于 Good。"""
        d, s, r = 5.0, 10.0, 0.9
        s_hard = self.engine._stability_after_recall(d, s, r, Rating.HARD)
        s_good = self.engine._stability_after_recall(d, s, r, Rating.GOOD)
        assert s_hard < s_good

    def test_lower_retrievability_more_growth(self):
        """回忆概率越低（越接近遗忘边缘），稳定性增长越多（间隔效应）。"""
        d, s = 5.0, 10.0
        s_high_r = self.engine._stability_after_recall(d, s, 0.95, Rating.GOOD)
        s_low_r = self.engine._stability_after_recall(d, s, 0.5, Rating.GOOD)
        assert s_low_r > s_high_r

    def test_higher_difficulty_less_growth(self):
        """难度越高，稳定性增长越少。"""
        s, r = 10.0, 0.9
        s_low_d = self.engine._stability_after_recall(2.0, s, r, Rating.GOOD)
        s_high_d = self.engine._stability_after_recall(9.0, s, r, Rating.GOOD)
        assert s_low_d > s_high_d


@pytest.mark.unit
class TestStabilityAfterForget:
    """测试遗忘后的稳定性更新。"""

    def setup_method(self):
        self.engine = FSRSEngine()

    def test_forget_reduces_stability(self):
        """遗忘后稳定性应低于原值。"""
        d, s, r = 5.0, 10.0, 0.5
        s_new = self.engine._stability_after_forget(d, s, r)
        assert s_new < s

    def test_higher_stability_retains_more(self):
        """原稳定性越高，遗忘后保留的稳定性越多。"""
        d, r = 5.0, 0.5
        s_low = self.engine._stability_after_forget(d, 5.0, r)
        s_high = self.engine._stability_after_forget(d, 20.0, r)
        assert s_high > s_low


@pytest.mark.unit
class TestReviewNewCard:
    """测试新卡片的复习流程。"""

    def setup_method(self):
        self.engine = FSRSEngine()
        self.now = datetime(2026, 1, 10, 10, 0)

    def test_new_card_good_rating(self):
        """新卡片评 Good：应初始化稳定性和难度，进入复习状态。"""
        card = Card()
        result = self.engine.review(card, Rating.GOOD, self.now)

        assert result.card.stability == DEFAULT_WEIGHTS[2]  # w[2] = 2.4
        assert result.card.difficulty == pytest.approx(DEFAULT_WEIGHTS[4])
        assert result.card.state == CardState.REVIEW
        assert result.card.reps == 1
        assert result.card.due is not None

    def test_new_card_again_rating(self):
        """新卡片评 Again：应进入学习状态。"""
        card = Card()
        result = self.engine.review(card, Rating.AGAIN, self.now)

        assert result.card.stability == DEFAULT_WEIGHTS[0]  # w[0] = 0.4
        assert result.card.state == CardState.LEARNING

    def test_new_card_easy_rating(self):
        """新卡片评 Easy：应有最高初始稳定性。"""
        card = Card()
        result = self.engine.review(card, Rating.EASY, self.now)

        assert result.card.stability == DEFAULT_WEIGHTS[3]  # w[3] = 5.8
        assert result.card.state == CardState.REVIEW

    def test_due_date_in_future(self):
        """复习后到期日应在未来。"""
        card = Card()
        result = self.engine.review(card, Rating.GOOD, self.now)
        assert result.card.due >= self.now.date()


@pytest.mark.unit
class TestReviewFlow:
    """测试完整复习流程（多轮复习）。"""

    def setup_method(self):
        self.engine = FSRSEngine()
        self.now = datetime(2026, 1, 10, 10, 0)

    def test_stability_grows_over_multiple_reviews(self):
        """多轮 Good 评分后稳定性应持续增长。"""
        card = Card()
        stabilities = []

        for i in range(10):
            review_time = self.now + timedelta(days=i * 5)
            result = self.engine.review(card, Rating.GOOD, review_time)
            stabilities.append(result.card.stability)

        # 稳定性应单调递增
        for i in range(1, len(stabilities)):
            assert stabilities[i] > stabilities[i - 1]

    def test_lapse_on_again_in_review(self):
        """复习状态评 Again 应增加 lapses 并进入重新学习。"""
        # 先让卡片进入复习状态
        card = Card()
        self.engine.review(card, Rating.GOOD, self.now)
        assert card.state == CardState.REVIEW

        # 一段时间后评 Again
        later = self.now + timedelta(days=3)
        result = self.engine.review(card, Rating.AGAIN, later)

        assert result.card.lapses == 1
        assert result.card.state == CardState.RELEARNING

    def test_stability_decreases_on_lapse(self):
        """遗忘后稳定性应降低（需多次复习建立足够稳定性后）。"""
        card = Card()
        # 多轮 Good 复习建立稳定性
        t = self.now
        for i in range(4):
            self.engine.review(card, Rating.GOOD, t)
            t = t + timedelta(days=max(1, card.due.toordinal() - t.toordinal()))
        s_before = card.stability
        assert s_before > 5.0  # 确保已建立足够稳定性

        # 长时间后遗忘
        later = t + timedelta(days=60)
        result = self.engine.review(card, Rating.AGAIN, later)

        assert result.card.stability < s_before

    def test_reps_increment(self):
        """每次复习 reps 应递增。"""
        card = Card()
        self.engine.review(card, Rating.GOOD, self.now)
        assert card.reps == 1

        later = self.now + timedelta(days=3)
        self.engine.review(card, Rating.GOOD, later)
        assert card.reps == 2

    def test_review_result_completeness(self):
        """ReviewResult 应包含完整的调度信息。"""
        card = Card()
        result = self.engine.review(card, Rating.GOOD, self.now)

        assert isinstance(result, ReviewResult)
        assert result.rating == Rating.GOOD
        assert result.review_time == self.now
        assert result.stability_before == 0.0
        assert result.stability_after > 0
        assert result.interval >= 1
        assert result.elapsed_days == 0.0  # 新卡片无上次复习


@pytest.mark.unit
class TestCardOrmConversion:
    """测试 Card 与 ReviewCard ORM 模型的互转。"""

    def test_from_orm(self, db_session):
        """从 ORM 模型转换为 Card 应正确映射所有字段。"""
        from app.models import KnowledgePoint, Question, ReviewCard, User

        user = User(username="fsrs_user", email="fsrs@test.com", password_hash="h")
        kp = KnowledgePoint(code="F-01", name="kp", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        q = Question(knowledge_point_id=kp.id, question_type="single_choice", content="c", answer="A")
        db_session.add(q)
        db_session.flush()

        orm_card = ReviewCard(
            user_id=user.id,
            question_id=q.id,
            knowledge_point_id=kp.id,
            stability=5.0,
            difficulty=6.0,
            due=date(2026, 1, 15),
            last_review=datetime(2026, 1, 10, 10, 0),
            reps=3,
            lapses=1,
            state="review",
        )
        db_session.add(orm_card)
        db_session.commit()

        card = Card.from_orm(orm_card)
        assert card.stability == 5.0
        assert card.difficulty == 6.0
        assert card.reps == 3
        assert card.lapses == 1
        assert card.state == CardState.REVIEW

    def test_to_orm(self, db_session):
        """将 Card 状态写回 ORM 模型应正确更新所有字段。"""
        from app.models import KnowledgePoint, Question, ReviewCard, User

        user = User(username="fsrs2_user", email="fsrs2@test.com", password_hash="h")
        kp = KnowledgePoint(code="F-02", name="kp", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        q = Question(knowledge_point_id=kp.id, question_type="single_choice", content="c", answer="A")
        db_session.add(q)
        db_session.flush()

        orm_card = ReviewCard(
            user_id=user.id,
            question_id=q.id,
            knowledge_point_id=kp.id,
            due=date(2026, 1, 15),
        )
        db_session.add(orm_card)
        db_session.commit()

        # 用引擎复习后写回
        engine = FSRSEngine()
        card = Card.from_orm(orm_card)
        engine.review(card, Rating.GOOD, datetime(2026, 1, 10, 10, 0))
        card.to_orm(orm_card)
        db_session.commit()

        db_session.refresh(orm_card)
        assert orm_card.stability > 0
        assert orm_card.state == "review"
        assert orm_card.reps == 1
