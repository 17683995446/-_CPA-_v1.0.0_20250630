"""
BKT (Bayesian Knowledge Tracing) 知识追踪引擎。

第一性原理：知识掌握是一个概率，而非二元状态。
学习者可能「知道但不小心答错」（slip），也可能「不知道但猜对」（guess）。
BKT 用贝叶斯推理从答题观测中更新对学习者知识状态的信念。

4 参数模型：
  - p_init (L₀):    初始掌握概率 P(known | start)
  - p_transit (T):  学习转移概率 P(unknown → known | practice)
  - p_guess (G):    猜对概率 P(correct | unknown)
  - p_slip (S):     失误概率 P(incorrect | known)

核心更新流程（每次答题后）：
  1. 预测：P(correct) = L * (1-S) + (1-L) * G
  2. 后验：L|obs = P(obs|L) * L / P(obs)
  3. 转移：L' = L|obs + (1 - L|obs) * T

参考：Corbett & Anderson (1995), "Knowledge Tracing: Modeling the Acquisition
of Human Knowledge"

业务规范：
- 每个用户对每个知识点维护独立的 BKT 参数
- p_known 是推荐系统和自适应难度的基础信号
- 支持「忘记」参数（可选第 5 参数），用于建模长期遗忘
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class MasteryState:
    """
    BKT 掌握度状态。

    纯数据对象，用于引擎计算和与 UserMastery ORM 模型互转。
    """
    p_known: float = 0.1     # 当前掌握概率
    p_transit: float = 0.3   # 学习转移概率
    p_guess: float = 0.25    # 猜对概率
    p_slip: float = 0.1      # 失误概率
    # 可选：忘记概率（BKT+Forget 扩展模型）
    p_forget: float = 0.0    # P(known → unknown | time)

    def __post_init__(self):
        """参数合法性校验。"""
        for name, val in [
            ("p_known", self.p_known),
            ("p_transit", self.p_transit),
            ("p_guess", self.p_guess),
            ("p_slip", self.p_slip),
            ("p_forget", self.p_forget),
        ]:
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{name} 必须在 [0, 1] 范围内，当前值: {val}")
        # guess 和 slip 应小于 0.5，否则模型不可辨识
        if self.p_guess >= 0.5:
            raise ValueError(f"p_guess 应小于 0.5，当前值: {self.p_guess}")
        if self.p_slip >= 0.5:
            raise ValueError(f"p_slip 应小于 0.5，当前值: {self.p_slip}")

    @classmethod
    def from_orm(cls, orm_mastery) -> "MasteryState":
        """从 UserMastery ORM 模型转换。"""
        return cls(
            p_known=orm_mastery.p_known,
            p_transit=orm_mastery.p_transit,
            p_guess=orm_mastery.p_guess,
            p_slip=orm_mastery.p_slip,
        )

    def to_orm(self, orm_mastery) -> None:
        """写回 UserMastery ORM 模型。"""
        orm_mastery.p_known = self.p_known
        orm_mastery.p_transit = self.p_transit
        orm_mastery.p_guess = self.p_guess
        orm_mastery.p_slip = self.p_slip


@dataclass
class BKTResult:
    """单次 BKT 更新的结果。"""
    state: MasteryState
    p_correct: float       # 预测的正确率
    p_known_before: float  # 更新前的掌握概率
    p_known_after: float   # 更新后的掌握概率
    is_correct: bool       # 本次答题是否正确


class BKTEngine:
    """
    BKT 知识追踪引擎。

    核心方法：
    - update(state, is_correct): 根据答题结果更新掌握度
    - predict(state): 预测下次答题的正确率
    - mastery_level(state): 返回掌握等级（用于推荐和自适应难度）

    使用方式：
        engine = BKTEngine()
        result = engine.update(state, is_correct=True)
    """

    def __init__(
        self,
        default_p_init: float = 0.1,
        default_p_transit: float = 0.3,
        default_p_guess: float = 0.25,
        default_p_slip: float = 0.1,
        default_p_forget: float = 0.0,
    ):
        self.defaults = MasteryState(
            p_known=default_p_init,
            p_transit=default_p_transit,
            p_guess=default_p_guess,
            p_slip=default_p_slip,
            p_forget=default_p_forget,
        )

    def predict(self, state: MasteryState) -> float:
        """
        预测下次答题的正确率。

        P(correct) = L * (1 - S) + (1 - L) * G

        其中：
        - L = p_known（当前掌握概率）
        - S = p_slip（知道但答错的概率）
        - G = p_guess（不知道但猜对的概率）
        """
        return state.p_known * (1 - state.p_slip) + (1 - state.p_known) * state.p_guess

    def update(self, state: MasteryState, is_correct: bool) -> BKTResult:
        """
        根据答题观测更新掌握度。

        两步贝叶斯更新：
        1. 后验更新：根据观测结果修正掌握概率
        2. 转移更新：考虑练习带来的学习效果

        参数：
        - state: 当前掌握度状态
        - is_correct: 本次答题是否正确

        返回：BKTResult，包含更新后的状态和预测信息
        """
        p_known_before = state.p_known
        p_correct = self.predict(state)

        # --- 步骤1：贝叶斯后验更新 ---
        if is_correct:
            # P(known | correct) = P(correct | known) * P(known) / P(correct)
            # = (1 - S) * L / P(correct)
            if p_correct > 0:
                p_known_posterior = (
                    state.p_known * (1 - state.p_slip) / p_correct
                )
            else:
                p_known_posterior = state.p_known
        else:
            # P(known | incorrect) = P(incorrect | known) * P(known) / P(incorrect)
            # = S * L / (1 - P(correct))
            p_incorrect = 1 - p_correct
            if p_incorrect > 0:
                p_known_posterior = (
                    state.p_known * state.p_slip / p_incorrect
                )
            else:
                p_known_posterior = state.p_known

        # 数值稳定性：确保在 [0, 1] 范围内
        p_known_posterior = max(0.0, min(1.0, p_known_posterior))

        # --- 步骤2：学习转移 ---
        # P'(known) = P(known|obs) + (1 - P(known|obs)) * T
        p_known_new = p_known_posterior + (1 - p_known_posterior) * state.p_transit

        # --- 可选：忘记效应 ---
        if state.p_forget > 0:
            # P''(known) = P'(known) * (1 - F)
            p_known_new = p_known_new * (1 - state.p_forget)

        # 数值稳定性
        p_known_new = max(0.0, min(1.0, p_known_new))

        # 更新状态
        state.p_known = p_known_new

        return BKTResult(
            state=state,
            p_correct=p_correct,
            p_known_before=p_known_before,
            p_known_after=p_known_new,
            is_correct=is_correct,
        )

    def update_batch(
        self, state: MasteryState, observations: list[bool]
    ) -> list[BKTResult]:
        """
        批量更新：按顺序处理多次答题观测。

        参数：
        - state: 初始掌握度状态（会被原地修改）
        - observations: 答题正确性序列

        返回：每次更新的结果列表
        """
        results = []
        for is_correct in observations:
            result = self.update(state, is_correct)
            results.append(result)
        return results

    def mastery_level(self, state: MasteryState) -> str:
        """
        返回掌握等级（用于 UI 展示和推荐系统）。

        等级划分：
        - "unknown":    p_known < 0.3  （几乎未掌握）
        - "learning":   0.3 ≤ p_known < 0.7  （学习中）
        - "mastering":  0.7 ≤ p_known < 0.95  （接近掌握）
        - "mastered":   p_known ≥ 0.95  （已掌握）
        """
        if state.p_known < 0.3:
            return "unknown"
        elif state.p_known < 0.7:
            return "learning"
        elif state.p_known < 0.95:
            return "mastering"
        else:
            return "mastered"

    def recommend_difficulty(self, state: MasteryState) -> int:
        """
        根据掌握度推荐题目难度（1-5）。

        第一性原理：心流理论要求挑战与能力匹配。
        - 低掌握度 → 低难度（建立信心）
        - 高掌握度 → 高难度（保持挑战）
        """
        level = state.p_known
        if level < 0.2:
            return 1
        elif level < 0.4:
            return 2
        elif level < 0.6:
            return 3
        elif level < 0.8:
            return 4
        else:
            return 5

    def create_initial_state(
        self,
        p_known: Optional[float] = None,
        p_transit: Optional[float] = None,
        p_guess: Optional[float] = None,
        p_slip: Optional[float] = None,
    ) -> MasteryState:
        """创建初始掌握度状态，未指定的参数使用默认值。"""
        return MasteryState(
            p_known=p_known if p_known is not None else self.defaults.p_known,
            p_transit=p_transit if p_transit is not None else self.defaults.p_transit,
            p_guess=p_guess if p_guess is not None else self.defaults.p_guess,
            p_slip=p_slip if p_slip is not None else self.defaults.p_slip,
        )
