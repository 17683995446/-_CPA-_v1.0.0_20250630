"""
游戏化激励引擎。

第一性原理：动机不是外加的装饰，而是学习循环的内生驱动力。
游戏化设计的核心不是「积分+徽章」（元分析显示无效），
而是「挑战+规则+反馈」的组合（d=0.50-0.52）。

基于循证教育心理学设计：
1. 心流自适应难度：挑战-能力平衡时注意力 73%（vs 不平衡 43%）
2. 连续学习+损失厌恶：Streak 断裂的恐惧驱动持续学习
3. 保护机制：消耗保护卡防止断签，减少挫折感
4. 变比奖励：随机奖励比固定奖励更能维持长期动机
5. 高难度成就：解锁高难度成就的用户留存率 74%（vs 32%）
6. 安全失败区：低风险练习降低焦虑（焦虑学习者错误率 2x）

业务规范：
- XP 来源：答对题目、连续学习、解锁成就
- 等级系统：指数增长的 XP 需求
- 成就系统：学习/连续/掌握/特殊 四类
- Streak：每日学习连续天数，配保护卡
"""
import random
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class AchievementCategory(str, Enum):
    """成就类别。"""
    LEARNING = "learning"      # 学习类（答题数等）
    STREAK = "streak"          # 连续学习类
    MASTERY = "mastery"        # 掌握度类
    SPECIAL = "special"        # 特殊成就


class FlowState(str, Enum):
    """心流状态（基于挑战-能力平衡）。"""
    BORED = "bored"          # 能力 >> 挑战 → 无聊
    FLOW = "flow"            # 能力 ≈ 挑战 → 心流
    ANXIETY = "anxiety"      # 能力 << 挑战 → 焦虑


@dataclass
class StreakInfo:
    """连续学习状态。"""
    streak_count: int = 0
    max_streak: int = 0
    protections: int = 1
    last_study_date: Optional[date] = None

    @classmethod
    def from_orm(cls, orm_streak) -> "StreakInfo":
        """从 UserStreak ORM 模型转换。"""
        return cls(
            streak_count=orm_streak.streak_count,
            max_streak=orm_streak.max_streak,
            protections=orm_streak.protections,
            last_study_date=orm_streak.last_study_date,
        )

    def to_orm(self, orm_streak) -> None:
        """写回 UserStreak ORM 模型。"""
        orm_streak.streak_count = self.streak_count
        orm_streak.max_streak = self.max_streak
        orm_streak.protections = self.protections
        orm_streak.last_study_date = self.last_study_date


@dataclass
class XPResult:
    """XP 奖励结果。"""
    base_xp: int
    bonus_xp: int
    total_xp: int
    reason: str  # 奖励原因描述
    is_critical: bool = False  # 是否为大额奖励（用于触发庆祝动画）


@dataclass
class LevelInfo:
    """等级信息。"""
    level: int
    current_level_xp: int   # 当前等级已获得的 XP
    next_level_xp: int      # 升到下一级所需的总 XP
    progress: float         # 当前等级进度 0-1


@dataclass
class AchievementCheckResult:
    """成就检查结果。"""
    unlocked_codes: list[str] = field(default_factory=list)
    total_xp_reward: int = 0


class GamificationEngine:
    """
    游戏化激励引擎。

    核心模块：
    - Streak 管理（连续学习 + 保护机制）
    - XP 计算（基础 + 变比奖励）
    - 等级系统（指数增长）
    - 成就检查
    - 心流自适应难度
    """

    # XP 配置（默认值，可被 config 覆盖）
    XP_PER_CORRECT: int = 10
    XP_PER_STREAK_DAY: int = 5
    XP_STREAK_BONUS_THRESHOLD: int = 7  # 连续 7 天起有额外奖励

    # 变比奖励配置
    CRITICAL_CHANCE: float = 0.1        # 10% 概率触发大额奖励
    CRITICAL_MULTIPLIER: float = 3.0    # 大额奖励倍数
    BONUS_RANGE: tuple[int, int] = (1, 5)  # 普通随机奖励范围

    # 等级配置
    BASE_LEVEL_XP: int = 100   # 1 级升 2 级所需 XP
    LEVEL_GROWTH_RATE: float = 1.5  # 每级 XP 需求增长率

    # Streak 配置
    STREAK_PROTECTION_MAX: int = 3  # 最大保护卡数量
    STREAK_PROTECTION_GAIN_INTERVAL: int = 7  # 每 7 天连续学习获得 1 张保护卡
    STREAK_PROTECTION_DEFAULT: int = 1  # 默认保护卡数量

    # 心流配置
    FLOW_BALANCE_THRESHOLD: float = 0.15  # 能力-挑战差值在 15% 内为心流

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        *,
        xp_per_correct: Optional[int] = None,
        xp_per_streak_day: Optional[int] = None,
        streak_protection_default: Optional[int] = None,
        critical_chance: Optional[float] = None,
        critical_multiplier: Optional[float] = None,
        base_level_xp: Optional[int] = None,
        level_growth_rate: Optional[float] = None,
        streak_protection_max: Optional[int] = None,
    ):
        """初始化引擎，参数可从 config 注入以消除配置双源。

        所有配置参数存为实例属性，避免修改类属性影响其他实例。
        """
        self.rng = rng or random.Random()
        # 实例级配置（不修改类属性，避免影响其他实例）
        self.xp_per_correct = xp_per_correct if xp_per_correct is not None else self.XP_PER_CORRECT
        self.xp_per_streak_day = xp_per_streak_day if xp_per_streak_day is not None else self.XP_PER_STREAK_DAY
        self.streak_protection_default = streak_protection_default if streak_protection_default is not None else self.STREAK_PROTECTION_DEFAULT
        self.critical_chance = critical_chance if critical_chance is not None else self.CRITICAL_CHANCE
        self.critical_multiplier = critical_multiplier if critical_multiplier is not None else self.CRITICAL_MULTIPLIER
        self.base_level_xp = base_level_xp if base_level_xp is not None else self.BASE_LEVEL_XP
        self.level_growth_rate = level_growth_rate if level_growth_rate is not None else self.LEVEL_GROWTH_RATE
        self.streak_protection_max = streak_protection_max if streak_protection_max is not None else self.STREAK_PROTECTION_MAX
        # 仅在显式传入时覆盖类常量，保持向后兼容
        if xp_per_correct is not None:
            self.XP_PER_CORRECT = xp_per_correct
        if xp_per_streak_day is not None:
            self.XP_PER_STREAK_DAY = xp_per_streak_day
        if streak_protection_default is not None:
            self.STREAK_PROTECTION_DEFAULT = streak_protection_default

    # ========== Streak 管理 ==========

    def update_streak(
        self, streak: StreakInfo, study_date: date
    ) -> tuple[StreakInfo, str]:
        """
        更新连续学习天数。

        逻辑：
        - 首次学习：streak = 1
        - 连续第二天：streak += 1
        - 断签一天：消耗保护卡保住 streak，否则重置为 1
        - 断签两天+：重置为 1

        返回：(更新后的 StreakInfo, 状态描述)
        """
        if streak.last_study_date is None:
            # 首次学习
            streak.streak_count = 1
            streak.last_study_date = study_date
            streak.max_streak = max(streak.max_streak, streak.streak_count)
            return streak, "首次学习，连续学习开始！"

        days_diff = (study_date - streak.last_study_date).days

        if days_diff == 0:
            # 当天已学习
            return streak, "今日已学习"

        elif days_diff == 1:
            # 连续学习
            streak.streak_count += 1
            streak.last_study_date = study_date
            streak.max_streak = max(streak.max_streak, streak.streak_count)

            # 检查是否获得保护卡
            if streak.streak_count % self.STREAK_PROTECTION_GAIN_INTERVAL == 0:
                if streak.protections < self.streak_protection_max:
                    streak.protections += 1
                    return streak, f"连续学习{streak.streak_count}天！获得保护卡×1"

            return streak, f"连续学习{streak.streak_count}天！"

        elif days_diff == 2:
            # 断签一天，尝试使用保护卡
            if streak.protections > 0:
                streak.protections -= 1
                streak.streak_count += 1
                streak.last_study_date = study_date
                streak.max_streak = max(streak.max_streak, streak.streak_count)
                return streak, f"消耗保护卡×1，连续学习保持{streak.streak_count}天"
            else:
                old_streak = streak.streak_count
                streak.streak_count = 1
                streak.last_study_date = study_date
                return streak, f"连续学习中断（原{old_streak}天），重新开始"

        else:
            # 断签两天以上，重置
            old_streak = streak.streak_count
            streak.streak_count = 1
            streak.last_study_date = study_date
            return streak, f"连续学习中断（原{old_streak}天），重新开始"

    def calculate_streak_xp(self, streak: StreakInfo) -> int:
        """计算连续学习奖励 XP。"""
        if streak.streak_count < self.XP_STREAK_BONUS_THRESHOLD:
            return streak.streak_count * self.xp_per_streak_day
        else:
            # 7 天起有额外加成
            base = streak.streak_count * self.xp_per_streak_day
            bonus = (streak.streak_count - self.XP_STREAK_BONUS_THRESHOLD + 1) * 10
            return base + bonus

    # ========== XP 计算 ==========

    def calculate_xp(
        self,
        is_correct: bool,
        difficulty: int = 3,
        streak: Optional[StreakInfo] = None,
    ) -> XPResult:
        """
        计算答题奖励 XP。

        策略：
        - 答对：基础 XP + 难度加成 + 变比奖励
        - 答错：少量安慰 XP（安全失败区设计）
        - 变比奖励：10% 概率触发 3x 大额奖励

        第一性原理：变比奖励（variable ratio schedule）比固定奖励
        更能维持长期动机（Skinner 操作性条件反射原理）。
        """
        if not is_correct:
            # 安全失败区：答错也给少量 XP，减少挫败感
            consolation = 1
            return XPResult(
                base_xp=consolation,
                bonus_xp=0,
                total_xp=consolation,
                reason="继续努力，每次尝试都是进步",
                is_critical=False,
            )

        # 基础 XP + 难度加成
        base_xp = self.xp_per_correct + (difficulty - 1) * 2

        # 变比奖励
        is_critical = self.rng.random() < self.critical_chance
        if is_critical:
            bonus_xp = int(base_xp * (self.critical_multiplier - 1))
            reason = f"完美！{self.critical_multiplier}x 奖励触发！"
        else:
            bonus_xp = self.rng.randint(*self.BONUS_RANGE)
            reason = "答对了！"

        total_xp = base_xp + bonus_xp

        return XPResult(
            base_xp=base_xp,
            bonus_xp=bonus_xp,
            total_xp=total_xp,
            reason=reason,
            is_critical=is_critical,
        )

    # ========== 等级系统 ==========

    def calculate_level(self, total_xp: int) -> LevelInfo:
        """
        根据总 XP 计算等级。

        等级 XP 需求呈指数增长：
        Level 1→2: 100 XP
        Level 2→3: 150 XP (100 * 1.5)
        Level 3→4: 225 XP (150 * 1.5)
        ...

        第 N 级升到 N+1 级需要: BASE * GROWTH^(N-1) XP
        到达第 N 级的累计 XP: BASE * (GROWTH^N - 1) / (GROWTH - 1)
        """
        if total_xp < self.base_level_xp:
            return LevelInfo(
                level=1,
                current_level_xp=total_xp,
                next_level_xp=self.base_level_xp,
                progress=total_xp / self.base_level_xp,
            )

        # 计算等级
        # 累计 XP 到达 N 级: BASE * (GROWTH^(N-1) - 1) / (GROWTH - 1)
        level = 1
        cumulative = 0
        level_xp_needed = self.base_level_xp

        while cumulative + level_xp_needed <= total_xp:
            cumulative += level_xp_needed
            level += 1
            level_xp_needed = int(self.base_level_xp * (self.level_growth_rate ** (level - 1)))

        current_level_xp = total_xp - cumulative
        progress = current_level_xp / level_xp_needed if level_xp_needed > 0 else 0

        return LevelInfo(
            level=level,
            current_level_xp=current_level_xp,
            next_level_xp=level_xp_needed,
            progress=min(1.0, progress),
        )

    def check_level_up(self, old_total_xp: int, new_total_xp: int) -> Optional[int]:
        """
        检查是否升级。

        返回：新等级（如果升级了），否则 None。
        """
        old_level = self.calculate_level(old_total_xp).level
        new_level = self.calculate_level(new_total_xp).level

        if new_level > old_level:
            return new_level
        return None

    # ========== 成就检查 ==========

    def check_achievements(
        self,
        user_stats: dict,
        unlocked_codes: set[str],
        achievement_defs: list[dict],
    ) -> AchievementCheckResult:
        """
        检查并解锁成就。

        参数：
        - user_stats: 用户当前统计 {total_xp, streak_days, correct_count, ...}
        - unlocked_codes: 已解锁的成就代码集合
        - achievement_defs: 成就定义列表 [{code, condition_type, condition_value, xp_reward}]

        返回：AchievementCheckResult
        """
        result = AchievementCheckResult()

        for ach in achievement_defs:
            if ach["code"] in unlocked_codes:
                continue

            condition_type = ach["condition_type"]
            condition_value = ach["condition_value"]
            current_value = user_stats.get(condition_type, 0)

            if current_value >= condition_value:
                result.unlocked_codes.append(ach["code"])
                result.total_xp_reward += ach.get("xp_reward", 0)

        return result

    # ========== 心流自适应难度 ==========

    def assess_flow_state(
        self, mastery_p_known: float, question_difficulty: int
    ) -> FlowState:
        """
        评估心流状态。

        第一性原理：心流发生在挑战与能力平衡时。
        - mastery_p_known: 用户当前知识掌握度 (0-1)
        - question_difficulty: 题目难度 (1-5)

        难度映射到 0-1 的挑战值：difficulty/5
        掌握度直接作为能力值
        差值在阈值内为心流
        """
        challenge = question_difficulty / 5.0
        ability = mastery_p_known

        diff = challenge - ability

        if abs(diff) <= self.FLOW_BALANCE_THRESHOLD:
            return FlowState.FLOW
        elif diff > 0:
            return FlowState.ANXIETY
        else:
            return FlowState.BORED

    def recommend_flow_difficulty(self, mastery_p_known: float) -> int:
        """
        基于心流理论推荐题目难度。

        目标：使挑战略高于能力（diff = +threshold/2），
        这是心流的最优入口点。
        """
        # 目标挑战值 = 能力 + 阈值/2
        target_challenge = mastery_p_known + self.FLOW_BALANCE_THRESHOLD / 2
        target_challenge = max(0.1, min(1.0, target_challenge))

        # 映射到 1-5 难度
        difficulty = round(target_challenge * 5)
        return max(1, min(5, difficulty))

    def get_safe_failure_recommendation(
        self, mastery_p_known: float, recent_error_rate: float
    ) -> dict:
        """
        安全失败区推荐。

        当用户近期错误率过高（焦虑状态）时，推荐降低难度或进入练习模式。
        """
        if recent_error_rate > 0.6 and mastery_p_known < 0.4:
            return {
                "mode": "practice",  # 练习模式（无 XP 惩罚）
                "reason": "近期错误率较高，建议先在练习模式巩固基础",
                "recommended_difficulty": max(1, self.recommend_flow_difficulty(mastery_p_known) - 1),
            }
        else:
            return {
                "mode": "normal",
                "reason": "状态良好，继续挑战",
                "recommended_difficulty": self.recommend_flow_difficulty(mastery_p_known),
            }

    # ========== 庆祝事件 ==========

    def should_celebrate(
        self,
        xp_result: Optional[XPResult] = None,
        level_up: Optional[int] = None,
        achievement_unlocked: Optional[str] = None,
        streak_milestone: Optional[int] = None,
    ) -> bool:
        """
        判断是否触发庆祝动画（峰终定律）。

        第一性原理：体验由最强时刻和结束时刻决定（峰终定律）。
        在关键时刻给予强烈正面反馈，强化记忆和动机。
        """
        if level_up is not None:
            return True
        if achievement_unlocked is not None:
            return True
        if xp_result and xp_result.is_critical:
            return True
        if streak_milestone and streak_milestone in (7, 14, 30, 50, 100):
            return True
        return False

    def get_zeigarnik_tension(
        self, incomplete_count: int, total_count: int
    ) -> Optional[str]:
        """
        蔡格尼克效应：未完成的任务会持续占据注意力。

        当有未完成的学习目标时，生成提醒文案驱动用户回来完成。
        """
        if total_count == 0:
            return None

        completion_rate = 1 - incomplete_count / total_count

        if incomplete_count > 0 and completion_rate > 0.5:
            return f"还有{incomplete_count}道题未完成，完成度{int(completion_rate*100)}%，继续加油！"
        elif incomplete_count > 0:
            return f"今日学习目标未完成，还差{incomplete_count}道题"
        else:
            return None
