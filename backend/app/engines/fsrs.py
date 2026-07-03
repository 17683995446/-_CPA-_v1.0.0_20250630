"""
FSRS (Free Spaced Repetition Scheduler) 间隔重复引擎。

第一性原理：记忆遵循「遗忘曲线」——回忆概率随时间衰减，
但每次成功回忆都会增强「记忆稳定性」，使衰减变慢。
FSRS 用三个变量精确描述这一过程：
  - Stability (S): 记忆稳定性（天）。S 越大，遗忘越慢。
  - Difficulty (D): 卡片难度 1-10。D 越高，稳定性增长越慢。
  - Retrievability (R): 当前回忆概率 0-1。R = (1 + t/(9*S))^(-1)

算法参考：FSRS-4.5 (L. Mai, H. Li, Y. Mai, KDD 2022)
开源实现：github.com/open-spaced-repetition

业务规范：
- 评分等级：1=Again(忘记) / 2=Hard / 3=Good / 4=Easy
- 卡片状态：new / learning / review / relearning
- 目标保持率默认 0.9（90%的卡片在到期日仍可回忆）
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import IntEnum
from typing import Optional


class Rating(IntEnum):
    """FSRS 评分等级。"""
    AGAIN = 1   # 完全忘记
    HARD = 2    # 回忆困难
    GOOD = 3    # 正常回忆
    EASY = 4    # 轻松回忆


class CardState(IntEnum):
    """FSRS 卡片状态。"""
    NEW = 0         # 未学习
    LEARNING = 1    # 学习中（短间隔）
    REVIEW = 2      # 复习中（长间隔）
    RELEARNING = 3  # 重新学习（遗忘后）


# FSRS-4.5 默认权重（17 个参数，通过 35 亿条复习数据训练得到）
DEFAULT_WEIGHTS: list[float] = [
    0.4,    # w[0]:  Again 初始稳定性
    0.6,    # w[1]:  Hard 初始稳定性
    2.4,    # w[2]:  Good 初始稳定性
    5.8,    # w[3]:  Easy 初始稳定性
    4.93,   # w[4]:  初始难度基准
    0.94,   # w[5]:  初始难度斜率（每级评分的变化量）
    0.86,   # w[6]:  难度更新权重
    0.01,   # w[7]:  均值回归权重
    1.49,   # w[8]:  回忆稳定性：exp 系数
    0.14,   # w[9]:  回忆稳定性：稳定性衰减指数
    0.94,   # w[10]: 回忆稳定性：可提取性衰减系数
    2.18,   # w[11]: 遗忘稳定性：基准系数
    0.05,   # w[12]: 遗忘稳定性：难度衰减指数
    0.34,   # w[13]: 遗忘稳定性：稳定性增长指数
    1.26,   # w[14]: 遗忘稳定性：可提取性衰减系数
    0.29,   # w[15]: Hard 惩罚乘数（<1，降低稳定性增长）
    2.61,   # w[16]: Easy 奖励乘数（>1，增加稳定性增长）
]


@dataclass
class Card:
    """
    FSRS 卡片状态。

    纯数据对象，不依赖数据库。用于引擎计算和与 ReviewCard ORM 模型互转。
    """
    stability: float = 0.0
    difficulty: float = 0.0
    due: Optional[date] = None
    last_review: Optional[datetime] = None
    reps: int = 0
    lapses: int = 0
    state: CardState = CardState.NEW

    @classmethod
    def from_orm(cls, orm_card) -> "Card":
        """从 ReviewCard ORM 模型转换为 Card。"""
        state_map = {
            "new": CardState.NEW,
            "learning": CardState.LEARNING,
            "review": CardState.REVIEW,
            "relearning": CardState.RELEARNING,
        }
        return cls(
            stability=orm_card.stability,
            difficulty=orm_card.difficulty,
            due=orm_card.due,
            last_review=orm_card.last_review,
            reps=orm_card.reps,
            lapses=orm_card.lapses,
            state=state_map.get(orm_card.state, CardState.NEW),
        )

    def to_orm(self, orm_card) -> None:
        """将 Card 状态写回 ReviewCard ORM 模型。"""
        state_map = {
            CardState.NEW: "new",
            CardState.LEARNING: "learning",
            CardState.REVIEW: "review",
            CardState.RELEARNING: "relearning",
        }
        orm_card.stability = self.stability
        orm_card.difficulty = self.difficulty
        orm_card.due = self.due
        orm_card.last_review = self.last_review
        orm_card.reps = self.reps
        orm_card.lapses = self.lapses
        orm_card.state = state_map[self.state]


@dataclass
class ReviewResult:
    """单次复习的计算结果。"""
    card: Card
    interval: int          # 安排的间隔（天）
    elapsed_days: float    # 距上次复习的天数
    retrievability: float  # 复习时的回忆概率
    stability_before: float
    difficulty_before: float
    stability_after: float
    difficulty_after: float
    rating: Rating
    review_time: datetime


class FSRSEngine:
    """
    FSRS 间隔重复引擎。

    核心方法：
    - review(card, rating, now): 执行一次复习，返回更新后的卡片和调度信息
    - retrievability(elapsed_days, stability): 计算回忆概率
    - next_interval(stability): 计算下次复习间隔

    使用方式：
        engine = FSRSEngine()
        result = engine.review(card, Rating.GOOD, datetime.now())
    """

    def __init__(
        self,
        weights: Optional[list[float]] = None,
        request_retention: float = 0.9,
        maximum_interval: int = 36500,
    ):
        self.w = weights if weights is not None else DEFAULT_WEIGHTS.copy()
        self.request_retention = request_retention
        self.maximum_interval = maximum_interval

    # ========== 核心公式 ==========

    def retrievability(self, elapsed_days: float, stability: float) -> float:
        """
        计算回忆概率（可提取性）。

        公式：R = (1 + t / (9 * S))^(-1)

        这是幂律遗忘曲线，比指数曲线更符合人类记忆的衰减规律。
        当 t=0 时 R=1（刚复习完，完全记得）；当 t→∞ 时 R→0。
        """
        if stability <= 0:
            return 0.0
        return (1.0 + elapsed_days / (9.0 * stability)) ** (-1)

    def next_interval(self, stability: float) -> int:
        """
        根据稳定性和目标保持率计算下次复习间隔（天）。

        公式：interval = S * 9 * (1/R_target - 1)

        这是 retrievability 的逆函数：给定目标保持率 R_target，
        求解 t 使得 R(t, S) = R_target。
        """
        interval = stability * 9.0 * (1.0 / self.request_retention - 1.0)
        return max(1, min(round(interval), self.maximum_interval))

    def _init_stability(self, rating: Rating) -> float:
        """初始稳定性：根据首次评分从权重中取值。"""
        return self.w[rating - 1]

    def _init_difficulty(self, rating: Rating) -> float:
        """初始难度：D0 = clamp(w[4] - (g-3)*w[5], 1, 10)。"""
        d = self.w[4] - (rating - 3) * self.w[5]
        return max(1.0, min(d, 10.0))

    def _next_difficulty(self, d: float, rating: Rating) -> float:
        """
        更新难度。

        D' = D - w[6] * (g - 3)
        D = mean_reversion(w[4], D')

        均值回归防止难度漂移过远：D = w[7] * D' + (1 - w[7]) * w[4]
        """
        next_d = d - self.w[6] * (rating - 3)
        reverted = self.w[7] * next_d + (1 - self.w[7]) * self.w[4]
        return max(1.0, min(reverted, 10.0))

    def _stability_after_recall(
        self, d: float, s: float, r: float, rating: Rating
    ) -> float:
        """
        回忆成功后的稳定性更新（Hard/Good/Easy）。

        公式：
        S' = S * (1 + exp(w[8]) * (11 - D) * S^(-w[9]) * (exp((1-R)*w[10]) - 1) * penalty * bonus)

        物理意义：
        - (11 - D): 难度越低，稳定性增长越多
        - S^(-w[9]): 稳定性越高，增长越慢（边际递减）
        - (exp((1-R)*w[10]) - 1): 回忆概率越低（越接近遗忘边缘），增长越多（间隔效应）
        - hard_penalty: Hard 评分降低增长
        - easy_bonus: Easy 评分增加增长
        """
        hard_penalty = self.w[15] if rating == Rating.HARD else 1.0
        easy_bonus = self.w[16] if rating == Rating.EASY else 1.0
        factor = (
            math.exp(self.w[8])
            * (11.0 - d)
            * (s ** (-self.w[9]))
            * (math.exp((1.0 - r) * self.w[10]) - 1.0)
            * hard_penalty
            * easy_bonus
        )
        return s * (1.0 + factor)

    def _stability_after_forget(
        self, d: float, s: float, r: float
    ) -> float:
        """
        遗忘后的稳定性更新（Again）。

        公式：
        S' = w[11] * D^(-w[12]) * (S+1)^w[13] * exp(w[14] * (1-R))

        物理意义：
        - D^(-w[12]): 难度越低，遗忘后新稳定性越高
        - (S+1)^w[13]: 原稳定性越高，遗忘后保留的稳定性越多
        - exp(w[14]*(1-R)): 回忆概率越低（遗忘越彻底），新稳定性越低
        """
        return (
            self.w[11]
            * (d ** (-self.w[12]))
            * ((s + 1.0) ** self.w[13])
            * math.exp(self.w[14] * (1.0 - r))
        )

    # ========== 主复习逻辑 ==========

    def review(
        self,
        card: Card,
        rating: Rating,
        now: Optional[datetime] = None,
    ) -> ReviewResult:
        """
        执行一次复习，更新卡片状态并返回调度结果。

        参数：
        - card: 复习前的卡片状态
        - rating: 用户评分 (1-4)
        - now: 复习时间（默认当前时间）

        返回：ReviewResult，包含更新后的卡片和完整调度信息
        """
        if now is None:
            now = datetime.now()

        # 记录复习前状态
        stability_before = card.stability
        difficulty_before = card.difficulty

        # 计算距离上次复习的天数
        if card.last_review is not None:
            elapsed_days = (now - card.last_review).total_seconds() / 86400.0
        else:
            elapsed_days = 0.0

        # 计算复习时的回忆概率
        r = self.retrievability(elapsed_days, card.stability)

        # 根据卡片状态和评分更新
        if card.state == CardState.NEW:
            self._review_new(card, rating, now)
        elif card.state in (CardState.LEARNING, CardState.RELEARNING):
            self._review_learning(card, rating, now)
        else:  # REVIEW
            self._review_recall(card, rating, now, elapsed_days, r)

        # 计算安排的间隔
        interval = self.next_interval(card.stability)

        # 学习/重新学习状态使用短间隔
        if card.state in (CardState.LEARNING, CardState.RELEARNING):
            # 学习阶段：Again→1天, Hard→1天, Good→1天+进入复习, Easy→2天+进入复习
            if rating == Rating.AGAIN:
                interval = 0  # 当天再练
            elif rating == Rating.HARD:
                interval = 1
            elif rating == Rating.GOOD:
                interval = max(1, interval)
                card.state = CardState.REVIEW
            elif rating == Rating.EASY:
                interval = max(2, interval)
                card.state = CardState.REVIEW

        # 更新到期日
        if interval == 0:
            card.due = now.date()
        else:
            card.due = now.date() + timedelta(days=interval)

        card.last_review = now
        card.reps += 1

        return ReviewResult(
            card=card,
            interval=interval,
            elapsed_days=elapsed_days,
            retrievability=r,
            stability_before=stability_before,
            difficulty_before=difficulty_before,
            stability_after=card.stability,
            difficulty_after=card.difficulty,
            rating=rating,
            review_time=now,
        )

    def _review_new(self, card: Card, rating: Rating, now: datetime) -> None:
        """新卡片的首次复习：初始化稳定性和难度。"""
        card.stability = self._init_stability(rating)
        card.difficulty = self._init_difficulty(rating)

        if rating == Rating.AGAIN:
            card.state = CardState.LEARNING
        else:
            # Hard/Good/Easy 直接进入学习或复习
            card.state = CardState.LEARNING
            if rating >= Rating.GOOD:
                card.state = CardState.REVIEW

    def _review_learning(self, card: Card, rating: Rating, now: datetime) -> None:
        """学习/重新学习状态的复习。"""
        if rating == Rating.AGAIN:
            card.lapses += 1 if card.state == CardState.RELEARNING else 0
            card.state = CardState.RELEARNING if card.state == CardState.REVIEW else card.state
            # 重置稳定性为遗忘后的值
            if card.stability > 0:
                r = self.retrievability(0, card.stability)
                card.stability = self._stability_after_forget(
                    card.difficulty, card.stability, r
                )
        else:
            card.difficulty = self._next_difficulty(card.difficulty, rating)
            if rating >= Rating.GOOD:
                card.state = CardState.REVIEW

    def _review_recall(
        self, card: Card, rating: Rating, now: datetime, elapsed_days: float, r: float
    ) -> None:
        """复习状态的复习：核心稳定性更新。"""
        card.difficulty = self._next_difficulty(card.difficulty, rating)

        if rating == Rating.AGAIN:
            # 遗忘：使用遗忘公式更新稳定性
            card.lapses += 1
            card.state = CardState.RELEARNING
            card.stability = self._stability_after_forget(
                card.difficulty, card.stability, r
            )
        else:
            # 回忆成功：使用回忆公式更新稳定性
            card.stability = self._stability_after_recall(
                card.difficulty, card.stability, r, rating
            )
