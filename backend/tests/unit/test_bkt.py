"""
阶段3 单元测试：BKT 知识追踪引擎。

测试范围：
- 参数合法性校验
- 预测公式正确性
- 贝叶斯后验更新（答对/答错）
- 学习转移效应
- 批量更新与收敛性
- 掌握等级与难度推荐
- ORM 模型互转
- 边界条件与数值稳定性
"""
import pytest

from app.engines.bkt import BKTEngine, BKTResult, MasteryState


@pytest.mark.unit
class TestMasteryStateValidation:
    """测试掌握度状态的参数校验。"""

    def test_valid_parameters(self):
        """合法参数应正常创建。"""
        state = MasteryState(p_known=0.3, p_transit=0.2, p_guess=0.2, p_slip=0.1)
        assert state.p_known == 0.3

    def test_default_values(self):
        """默认值应符合 BKT 标准。"""
        state = MasteryState()
        assert state.p_known == 0.1
        assert state.p_transit == 0.3
        assert state.p_guess == 0.25
        assert state.p_slip == 0.1
        assert state.p_forget == 0.0

    def test_p_known_out_of_range(self):
        """p_known 超出 [0,1] 应报错。"""
        with pytest.raises(ValueError):
            MasteryState(p_known=1.5)

    def test_p_known_negative(self):
        """p_known 为负应报错。"""
        with pytest.raises(ValueError):
            MasteryState(p_known=-0.1)

    def test_guess_too_high(self):
        """p_guess >= 0.5 应报错（模型不可辨识）。"""
        with pytest.raises(ValueError):
            MasteryState(p_guess=0.5)

    def test_slip_too_high(self):
        """p_slip >= 0.5 应报错。"""
        with pytest.raises(ValueError):
            MasteryState(p_slip=0.6)


@pytest.mark.unit
class TestPrediction:
    """测试正确率预测公式。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_full_mastery_high_correct(self):
        """完全掌握时（L=1, S=0），正确率应为 1.0。"""
        state = MasteryState(p_known=1.0, p_slip=0.0)
        assert self.engine.predict(state) == pytest.approx(1.0)

    def test_no_mastery_with_no_guess(self):
        """未掌握且无法猜对时（L=0, G=0），正确率应为 0。"""
        state = MasteryState(p_known=0.0, p_guess=0.0)
        assert self.engine.predict(state) == pytest.approx(0.0)

    def test_formula_exact(self):
        """验证 P(correct) = L*(1-S) + (1-L)*G 的精确值。"""
        state = MasteryState(p_known=0.5, p_transit=0.3, p_guess=0.2, p_slip=0.1)
        expected = 0.5 * (1 - 0.1) + (1 - 0.5) * 0.2  # 0.45 + 0.10 = 0.55
        assert self.engine.predict(state) == pytest.approx(expected)

    def test_higher_mastery_higher_correct(self):
        """掌握度越高，预测正确率越高。"""
        state_low = MasteryState(p_known=0.2)
        state_high = MasteryState(p_known=0.8)
        assert self.engine.predict(state_high) > self.engine.predict(state_low)


@pytest.mark.unit
class TestUpdateCorrect:
    """测试答对后的掌握度更新。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_correct_increases_mastery(self):
        """答对应增加掌握概率。"""
        state = MasteryState(p_known=0.3)
        result = self.engine.update(state, is_correct=True)
        assert result.p_known_after > result.p_known_before

    def test_correct_posterior_formula(self):
        """验证答对后的后验概率公式。"""
        state = MasteryState(p_known=0.5, p_transit=0.0, p_guess=0.2, p_slip=0.1)
        # P(correct) = 0.5*0.9 + 0.5*0.2 = 0.55
        # P(known|correct) = 0.5*0.9 / 0.55 = 0.8181...
        # With T=0, no transition
        result = self.engine.update(state, is_correct=True)
        expected = 0.5 * 0.9 / 0.55
        assert result.p_known_after == pytest.approx(expected, rel=1e-4)

    def test_transition_adds_learning(self):
        """学习转移应额外增加掌握概率。"""
        state_no_transit = MasteryState(p_known=0.5, p_transit=0.0)
        state_with_transit = MasteryState(p_known=0.5, p_transit=0.3)

        self.engine.update(state_no_transit, is_correct=True)
        self.engine.update(state_with_transit, is_correct=True)

        assert state_with_transit.p_known > state_no_transit.p_known

    def test_correct_result_fields(self):
        """BKTResult 应包含完整信息。"""
        state = MasteryState(p_known=0.3)
        result = self.engine.update(state, is_correct=True)

        assert isinstance(result, BKTResult)
        assert result.is_correct is True
        assert result.p_correct > 0
        assert result.p_known_before == 0.3
        assert result.p_known_after > 0.3


@pytest.mark.unit
class TestUpdateIncorrect:
    """测试答错后的掌握度更新。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_incorrect_decreases_mastery(self):
        """答错应降低掌握概率。"""
        state = MasteryState(p_known=0.7)
        result = self.engine.update(state, is_correct=False)
        assert result.p_known_after < result.p_known_before

    def test_incorrect_posterior_formula(self):
        """验证答错后的后验概率公式。"""
        state = MasteryState(p_known=0.5, p_transit=0.0, p_guess=0.2, p_slip=0.1)
        # P(correct) = 0.55, P(incorrect) = 0.45
        # P(known|incorrect) = 0.5*0.1 / 0.45 = 0.1111...
        result = self.engine.update(state, is_correct=False)
        expected = 0.5 * 0.1 / 0.45
        assert result.p_known_after == pytest.approx(expected, rel=1e-4)

    def test_incorrect_with_transition(self):
        """答错后仍有学习转移（练习本身有学习效果）。"""
        state = MasteryState(p_known=0.5, p_transit=0.3, p_guess=0.2, p_slip=0.1)
        result = self.engine.update(state, is_correct=False)
        # 后验降低，但转移会拉回一些
        # P(known|incorrect) = 0.5*0.1/0.45 = 0.1111
        # P'(known) = 0.1111 + (1-0.1111)*0.3 = 0.1111 + 0.2667 = 0.3778
        assert 0.1 < result.p_known_after < 0.5  # 介于后验和转移后之间


@pytest.mark.unit
class TestBatchUpdate:
    """测试批量更新与收敛性。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_all_correct_converges_to_high_mastery(self):
        """连续答对应使掌握概率趋近 1。"""
        state = MasteryState(p_known=0.1, p_transit=0.3)
        results = self.engine.update_batch(state, [True] * 20)

        assert state.p_known > 0.9
        # 掌握概率应单调递增
        for i in range(1, len(results)):
            assert results[i].p_known_after >= results[i - 1].p_known_after

    def test_all_incorrect_converges_to_low(self):
        """连续答错应使掌握概率趋近 0。"""
        state = MasteryState(p_known=0.9, p_transit=0.0, p_guess=0.1, p_slip=0.1)
        self.engine.update_batch(state, [False] * 20)

        assert state.p_known < 0.1

    def test_mixed_sequence(self):
        """交替答对答错应使掌握概率在合理范围波动（不趋向极端）。"""
        state = MasteryState(p_known=0.5, p_transit=0.2)
        observations = [True, False, True, False, True, True, False, True]
        self.engine.update_batch(state, observations)

        # 5/8 正确率，掌握概率应在中高区域但未达 1.0
        assert 0.5 < state.p_known < 1.0

    def test_batch_returns_correct_count(self):
        """批量更新应返回与观测数相同的结果。"""
        state = MasteryState()
        results = self.engine.update_batch(state, [True, False, True])
        assert len(results) == 3


@pytest.mark.unit
class TestMasteryLevel:
    """测试掌握等级划分。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_unknown_level(self):
        """p_known < 0.3 应为 unknown。"""
        state = MasteryState(p_known=0.2)
        assert self.engine.mastery_level(state) == "unknown"

    def test_learning_level(self):
        """0.3 ≤ p_known < 0.7 应为 learning。"""
        state = MasteryState(p_known=0.5)
        assert self.engine.mastery_level(state) == "learning"

    def test_mastering_level(self):
        """0.7 ≤ p_known < 0.95 应为 mastering。"""
        state = MasteryState(p_known=0.8)
        assert self.engine.mastery_level(state) == "mastering"

    def test_mastered_level(self):
        """p_known ≥ 0.95 应为 mastered。"""
        state = MasteryState(p_known=0.97)
        assert self.engine.mastery_level(state) == "mastered"


@pytest.mark.unit
class TestDifficultyRecommendation:
    """测试难度推荐。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_low_mastery_low_difficulty(self):
        """低掌握度应推荐低难度。"""
        state = MasteryState(p_known=0.1)
        assert self.engine.recommend_difficulty(state) == 1

    def test_high_mastery_high_difficulty(self):
        """高掌握度应推荐高难度。"""
        state = MasteryState(p_known=0.9)
        assert self.engine.recommend_difficulty(state) == 5

    def test_monotonic_increase(self):
        """掌握度越高，推荐难度越高或相等。"""
        levels = [0.1, 0.3, 0.5, 0.7, 0.9]
        difficulties = [
            self.engine.recommend_difficulty(MasteryState(p_known=l))
            for l in levels
        ]
        for i in range(1, len(difficulties)):
            assert difficulties[i] >= difficulties[i - 1]

    def test_range_1_to_5(self):
        """推荐难度应在 1-5 范围内。"""
        for p in [0.0, 0.25, 0.5, 0.75, 1.0]:
            d = self.engine.recommend_difficulty(MasteryState(p_known=p))
            assert 1 <= d <= 5


@pytest.mark.unit
class TestForgetEffect:
    """测试忘记效应（BKT+Forget 扩展）。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_forget_reduces_mastery(self):
        """有忘记效应时，掌握概率增长更慢。"""
        state_no_forget = MasteryState(p_known=0.5, p_transit=0.3, p_forget=0.0)
        state_with_forget = MasteryState(p_known=0.5, p_transit=0.3, p_forget=0.1)

        self.engine.update(state_no_forget, is_correct=True)
        self.engine.update(state_with_forget, is_correct=True)

        assert state_with_forget.p_known < state_no_forget.p_known

    def test_forget_long_term_equilibrium(self):
        """有忘记效应时，长期答对也不会达到 1.0。"""
        state = MasteryState(p_known=0.1, p_transit=0.3, p_forget=0.05)
        self.engine.update_batch(state, [True] * 50)
        assert state.p_known < 1.0


@pytest.mark.unit
class TestEdgeCases:
    """测试边界条件与数值稳定性。"""

    def setup_method(self):
        self.engine = BKTEngine()

    def test_zero_mastery_correct(self):
        """p_known=0 时答对，后验应基于猜对概率。"""
        state = MasteryState(p_known=0.0, p_transit=0.0, p_guess=0.25, p_slip=0.1)
        result = self.engine.update(state, is_correct=True)
        # P(correct) = 0 * 0.9 + 1 * 0.25 = 0.25
        # P(known|correct) = 0 * 0.9 / 0.25 = 0
        assert result.p_known_after == pytest.approx(0.0)

    def test_full_mastery_incorrect(self):
        """p_known=1 时答错，后验应基于失误概率。"""
        state = MasteryState(p_known=1.0, p_transit=0.0, p_guess=0.25, p_slip=0.1)
        result = self.engine.update(state, is_correct=False)
        # P(correct) = 1 * 0.9 + 0 * 0.25 = 0.9
        # P(known|incorrect) = 1 * 0.1 / 0.1 = 1.0
        assert result.p_known_after == pytest.approx(1.0)

    def test_result_in_valid_range(self):
        """更新后 p_known 应始终在 [0, 1] 范围内。"""
        state = MasteryState(p_known=0.99, p_transit=0.9)
        result = self.engine.update(state, is_correct=True)
        assert 0.0 <= result.p_known_after <= 1.0


@pytest.mark.unit
class TestOrmConversion:
    """测试 MasteryState 与 UserMastery ORM 模型的互转。"""

    def test_from_orm(self, db_session):
        """从 ORM 模型转换应正确映射。"""
        from app.models import KnowledgePoint, User, UserMastery

        user = User(username="bkt_user", email="bkt@test.com", password_hash="h")
        kp = KnowledgePoint(code="B-01", name="bkt_kp", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        mastery = UserMastery(
            user_id=user.id,
            knowledge_point_id=kp.id,
            p_known=0.65,
            p_transit=0.25,
            p_guess=0.15,
            p_slip=0.08,
        )
        db_session.add(mastery)
        db_session.commit()

        state = MasteryState.from_orm(mastery)
        assert state.p_known == 0.65
        assert state.p_transit == 0.25
        assert state.p_guess == 0.15
        assert state.p_slip == 0.08

    def test_to_orm(self, db_session):
        """写回 ORM 模型应正确更新。"""
        from app.models import KnowledgePoint, User, UserMastery

        user = User(username="bkt2_user", email="bkt2@test.com", password_hash="h")
        kp = KnowledgePoint(code="B-02", name="bkt_kp2", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()

        mastery = UserMastery(user_id=user.id, knowledge_point_id=kp.id)
        db_session.add(mastery)
        db_session.commit()

        # 用引擎更新后写回
        engine = BKTEngine()
        state = MasteryState.from_orm(mastery)
        engine.update(state, is_correct=True)
        state.to_orm(mastery)
        db_session.commit()

        db_session.refresh(mastery)
        assert mastery.p_known > 0.1  # 应从初始 0.1 增长
