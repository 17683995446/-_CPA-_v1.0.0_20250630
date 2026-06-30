"""
阶段5 单元测试：游戏化激励引擎。

测试范围：
- Streak 管理（连续学习、保护机制、断签处理）
- XP 计算（基础奖励、变比奖励、难度加成）
- 等级系统（指数增长、升级检测）
- 成就检查（条件判断、批量解锁）
- 心流自适应难度（挑战-能力平衡）
- 安全失败区（高错误率降级）
- 庆祝事件（峰终定律）
- 蔡格尼克效应（未完成张力）
"""
import random
from datetime import date, timedelta

import pytest

from app.engines.gamification import (
    AchievementCategory,
    AchievementCheckResult,
    FlowState,
    GamificationEngine,
    LevelInfo,
    StreakInfo,
    XPResult,
)


@pytest.mark.unit
class TestStreakManagement:
    """测试连续学习管理。"""

    def setup_method(self):
        self.engine = GamificationEngine(rng=random.Random(42))

    def test_first_study(self):
        """首次学习应设置 streak=1。"""
        streak = StreakInfo()
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 10))

        assert updated.streak_count == 1
        assert updated.last_study_date == date(2026, 1, 10)
        assert updated.max_streak == 1
        assert "首次" in msg

    def test_consecutive_days(self):
        """连续学习应递增 streak。"""
        streak = StreakInfo()
        self.engine.update_streak(streak, date(2026, 1, 10))
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 11))

        assert updated.streak_count == 2
        assert "连续学习2天" in msg

    def test_same_day_no_change(self):
        """当天重复学习不改变 streak。"""
        streak = StreakInfo()
        self.engine.update_streak(streak, date(2026, 1, 10))
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 10))

        assert updated.streak_count == 1
        assert "今日已学习" in msg

    def test_break_with_protection(self):
        """断签一天，有保护卡时应保住 streak。"""
        streak = StreakInfo(streak_count=5, protections=1, last_study_date=date(2026, 1, 10))
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 12))

        assert updated.streak_count == 6  # 保住并 +1
        assert updated.protections == 0   # 消耗了一张
        assert "保护卡" in msg

    def test_break_without_protection(self):
        """断签一天，无保护卡时应重置 streak。"""
        streak = StreakInfo(streak_count=5, protections=0, last_study_date=date(2026, 1, 10))
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 12))

        assert updated.streak_count == 1  # 重置
        assert "中断" in msg

    def test_break_two_days_reset(self):
        """断签两天以上应直接重置。"""
        streak = StreakInfo(streak_count=10, protections=1, last_study_date=date(2026, 1, 10))
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 14))

        assert updated.streak_count == 1
        assert updated.protections == 1  # 保护卡未被消耗
        assert "中断" in msg

    def test_protection_earned_every_7_days(self):
        """每连续学习 7 天应获得一张保护卡。"""
        streak = StreakInfo(streak_count=6, protections=0, last_study_date=date(2026, 1, 10))
        updated, msg = self.engine.update_streak(streak, date(2026, 1, 11))

        assert updated.streak_count == 7
        assert updated.protections == 1
        assert "保护卡" in msg

    def test_protection_max_limit(self):
        """保护卡不应超过最大值。"""
        streak = StreakInfo(
            streak_count=6, protections=self.engine.STREAK_PROTECTION_MAX,
            last_study_date=date(2026, 1, 10),
        )
        updated, _ = self.engine.update_streak(streak, date(2026, 1, 11))

        assert updated.protections == self.engine.STREAK_PROTECTION_MAX

    def test_max_streak_updated(self):
        """max_streak 应记录历史最高。"""
        streak = StreakInfo(streak_count=5, max_streak=3, last_study_date=date(2026, 1, 10))
        updated, _ = self.engine.update_streak(streak, date(2026, 1, 11))

        assert updated.max_streak == 6  # 新纪录


@pytest.mark.unit
class TestXPCalculation:
    """测试 XP 计算。"""

    def test_correct_answer_base_xp(self):
        """答对应获得基础 XP。"""
        engine = GamificationEngine(rng=random.Random(42))
        result = engine.calculate_xp(is_correct=True, difficulty=3)

        assert result.base_xp >= GamificationEngine.XP_PER_CORRECT
        assert result.total_xp > 0

    def test_incorrect_answer_consolation(self):
        """答错应获得少量安慰 XP。"""
        engine = GamificationEngine(rng=random.Random(42))
        result = engine.calculate_xp(is_correct=False, difficulty=3)

        assert result.total_xp == 1  # 安慰 XP
        assert not result.is_critical

    def test_difficulty_bonus(self):
        """高难度应获得更多基础 XP。"""
        engine = GamificationEngine(rng=random.Random(42))
        easy = engine.calculate_xp(is_correct=True, difficulty=1)
        hard = engine.calculate_xp(is_correct=True, difficulty=5)

        assert hard.base_xp > easy.base_xp

    def test_variable_reward_critical(self):
        """应有概率触发大额奖励。"""
        # 用大量样本验证概率
        engine = GamificationEngine()
        critical_count = 0
        trials = 1000

        for _ in range(trials):
            result = engine.calculate_xp(is_correct=True, difficulty=3)
            if result.is_critical:
                critical_count += 1

        # 期望约 10% 的触发率
        assert 50 < critical_count < 200  # 宽松范围

    def test_critical_higher_than_normal(self):
        """大额奖励应比普通奖励高。"""
        engine = GamificationEngine(rng=random.Random(42))

        # 找到一个大额奖励
        critical_result = None
        for _ in range(100):
            r = engine.calculate_xp(is_correct=True, difficulty=3)
            if r.is_critical:
                critical_result = r
                break

        normal_result = engine.calculate_xp(is_correct=True, difficulty=3)
        # 暂时强制非 critical
        while normal_result.is_critical:
            normal_result = engine.calculate_xp(is_correct=True, difficulty=3)

        if critical_result:
            assert critical_result.total_xp > normal_result.base_xp


@pytest.mark.unit
class TestLevelSystem:
    """测试等级系统。"""

    def setup_method(self):
        self.engine = GamificationEngine()

    def test_level_1_zero_xp(self):
        """0 XP 应为 1 级。"""
        info = self.engine.calculate_level(0)
        assert info.level == 1

    def test_level_2_at_100_xp(self):
        """100 XP 应为 2 级。"""
        info = self.engine.calculate_level(100)
        assert info.level == 2

    def test_level_progress(self):
        """等级进度应在 0-1 范围内。"""
        info = self.engine.calculate_level(50)
        assert 0 < info.progress < 1
        assert info.current_level_xp == 50

    def test_exponential_growth(self):
        """等级 XP 需求应指数增长。"""
        level1_to_2 = self.engine.calculate_level(0).next_level_xp
        level2_info = self.engine.calculate_level(100)
        level2_to_3 = level2_info.next_level_xp

        assert level2_to_3 > level1_to_2  # 下一级需要更多 XP

    def test_check_level_up(self):
        """应正确检测升级。"""
        assert self.engine.check_level_up(90, 110) == 2  # 跨越 1→2
        assert self.engine.check_level_up(50, 60) is None  # 未升级
        assert self.engine.check_level_up(100, 250) == 3   # 跨越 2→3

    def test_high_level(self):
        """高 XP 应对应高等级。"""
        info = self.engine.calculate_level(10000)
        assert info.level >= 5


@pytest.mark.unit
class TestAchievementCheck:
    """测试成就检查。"""

    def setup_method(self):
        self.engine = GamificationEngine()

    def test_unlock_when_condition_met(self):
        """条件满足时应解锁成就。"""
        achievements = [
            {"code": "first_correct", "condition_type": "correct_count",
             "condition_value": 1, "xp_reward": 10},
        ]
        user_stats = {"correct_count": 5}
        result = self.engine.check_achievements(user_stats, set(), achievements)

        assert "first_correct" in result.unlocked_codes
        assert result.total_xp_reward == 10

    def test_skip_already_unlocked(self):
        """已解锁的成就不应重复解锁。"""
        achievements = [
            {"code": "first_correct", "condition_type": "correct_count",
             "condition_value": 1, "xp_reward": 10},
        ]
        user_stats = {"correct_count": 100}
        result = self.engine.check_achievements(
            user_stats, {"first_correct"}, achievements
        )

        assert len(result.unlocked_codes) == 0

    def test_condition_not_met(self):
        """条件未满足时不应解锁。"""
        achievements = [
            {"code": "streak_30", "condition_type": "streak_days",
             "condition_value": 30, "xp_reward": 100},
        ]
        user_stats = {"streak_days": 5}
        result = self.engine.check_achievements(user_stats, set(), achievements)

        assert len(result.unlocked_codes) == 0

    def test_multiple_unlocks(self):
        """应能同时解锁多个成就。"""
        achievements = [
            {"code": "a1", "condition_type": "correct_count", "condition_value": 10, "xp_reward": 20},
            {"code": "a2", "condition_type": "total_xp", "condition_value": 100, "xp_reward": 50},
            {"code": "a3", "condition_type": "streak_days", "condition_value": 100, "xp_reward": 200},
        ]
        user_stats = {"correct_count": 15, "total_xp": 200, "streak_days": 5}
        result = self.engine.check_achievements(user_stats, set(), achievements)

        assert len(result.unlocked_codes) == 2  # a1 和 a2
        assert result.total_xp_reward == 70


@pytest.mark.unit
class TestFlowState:
    """测试心流自适应难度。"""

    def setup_method(self):
        self.engine = GamificationEngine()

    def test_flow_when_balanced(self):
        """挑战-能力平衡时应为心流状态。"""
        # 掌握度 0.6，难度 3 (0.6) → 差值 0 → 心流
        state = self.engine.assess_flow_state(0.6, 3)
        assert state == FlowState.FLOW

    def test_anxiety_when_too_hard(self):
        """挑战远高于能力时应为焦虑状态。"""
        # 掌握度 0.2，难度 5 (1.0) → 差值 0.8 → 焦虑
        state = self.engine.assess_flow_state(0.2, 5)
        assert state == FlowState.ANXIETY

    def test_bored_when_too_easy(self):
        """能力远高于挑战时应为无聊状态。"""
        # 掌握度 0.9，难度 1 (0.2) → 差值 -0.7 → 无聊
        state = self.engine.assess_flow_state(0.9, 1)
        assert state == FlowState.BORED

    def test_recommend_difficulty_increases_with_mastery(self):
        """掌握度越高，推荐难度越高。"""
        d_low = self.engine.recommend_flow_difficulty(0.1)
        d_high = self.engine.recommend_flow_difficulty(0.9)
        assert d_high >= d_low

    def test_recommend_difficulty_in_range(self):
        """推荐难度应在 1-5 范围内。"""
        for mastery in [0.0, 0.25, 0.5, 0.75, 1.0]:
            d = self.engine.recommend_flow_difficulty(mastery)
            assert 1 <= d <= 5

    def test_recommend_creates_flow(self):
        """推荐难度应使大部分场景进入心流状态。"""
        for mastery in [0.2, 0.4, 0.6, 0.8]:
            d = self.engine.recommend_flow_difficulty(mastery)
            state = self.engine.assess_flow_state(mastery, d)
            # 至少不应该焦虑
            assert state != FlowState.ANXIETY


@pytest.mark.unit
class TestSafeFailureZone:
    """测试安全失败区。"""

    def setup_method(self):
        self.engine = GamificationEngine()

    def test_high_error_rate_practice_mode(self):
        """高错误率 + 低掌握度应推荐练习模式。"""
        rec = self.engine.get_safe_failure_recommendation(
            mastery_p_known=0.2, recent_error_rate=0.7
        )
        assert rec["mode"] == "practice"
        assert rec["recommended_difficulty"] >= 1

    def test_normal_state_normal_mode(self):
        """正常状态应推荐普通模式。"""
        rec = self.engine.get_safe_failure_recommendation(
            mastery_p_known=0.6, recent_error_rate=0.3
        )
        assert rec["mode"] == "normal"

    def test_high_mastery_with_errors_stays_normal(self):
        """高掌握度即使有错误也保持普通模式。"""
        rec = self.engine.get_safe_failure_recommendation(
            mastery_p_known=0.8, recent_error_rate=0.5
        )
        assert rec["mode"] == "normal"


@pytest.mark.unit
class TestCelebration:
    """测试庆祝事件（峰终定律）。"""

    def setup_method(self):
        self.engine = GamificationEngine()

    def test_level_up_celebrates(self):
        """升级应触发庆祝。"""
        assert self.engine.should_celebrate(level_up=5) is True

    def test_achievement_celebrates(self):
        """解锁成就应触发庆祝。"""
        assert self.engine.should_celebrate(achievement_unlocked="streak_30") is True

    def test_critical_xp_celebrates(self):
        """大额奖励应触发庆祝。"""
        xp_result = XPResult(base_xp=10, bonus_xp=20, total_xp=30, reason=" Critical!", is_critical=True)
        assert self.engine.should_celebrate(xp_result=xp_result) is True

    def test_streak_milestone_celebrates(self):
        """连续学习里程碑应触发庆祝。"""
        for milestone in [7, 14, 30, 50, 100]:
            assert self.engine.should_celebrate(streak_milestone=milestone) is True

    def test_no_celebration_for_normal(self):
        """普通事件不应触发庆祝。"""
        assert self.engine.should_celebrate() is False

    def test_non_milestone_streak_no_celebrate(self):
        """非里程碑的连续天数不应触发庆祝。"""
        assert self.engine.should_celebrate(streak_milestone=6) is False


@pytest.mark.unit
class TestZeigarnikEffect:
    """测试蔡格尼克效应（未完成张力）。"""

    def setup_method(self):
        self.engine = GamificationEngine()

    def test_incomplete_generates_tension(self):
        """未完成任务应生成提醒。"""
        tension = self.engine.get_zeigarnik_tension(5, 20)
        assert tension is not None
        assert "5" in tension  # 包含未完成数量

    def test_complete_no_tension(self):
        """全部完成时不应有张力。"""
        tension = self.engine.get_zeigarnik_tension(0, 20)
        assert tension is None

    def test_empty_no_tension(self):
        """无任务时不应有张力。"""
        tension = self.engine.get_zeigarnik_tension(0, 0)
        assert tension is None

    def test_high_completion_rate_message(self):
        """高完成率时应有鼓励性消息。"""
        tension = self.engine.get_zeigarnik_tension(2, 20)
        assert tension is not None
        assert "90%" in tension or "完成度" in tension


@pytest.mark.unit
class TestOrmConversion:
    """测试 StreakInfo 与 UserStreak ORM 模型的互转。"""

    def test_streak_orm_conversion(self, db_session):
        """StreakInfo 应能正确与 ORM 模型互转。"""
        from app.models import User, UserStreak

        user = User(username="game_user", email="game@test.com", password_hash="h")
        db_session.add(user)
        db_session.flush()

        orm_streak = UserStreak(
            user_id=user.id,
            streak_count=7,
            max_streak=10,
            protections=2,
            last_study_date=date(2026, 1, 10),
        )
        db_session.add(orm_streak)
        db_session.commit()

        # 从 ORM 转换
        info = StreakInfo.from_orm(orm_streak)
        assert info.streak_count == 7
        assert info.max_streak == 10
        assert info.protections == 2

        # 更新后写回
        engine = GamificationEngine()
        engine.update_streak(info, date(2026, 1, 11))
        info.to_orm(orm_streak)
        db_session.commit()

        db_session.refresh(orm_streak)
        assert orm_streak.streak_count == 8
