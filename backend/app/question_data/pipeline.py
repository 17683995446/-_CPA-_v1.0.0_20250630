"""题库数据修复流水线。

提供通用的修复步骤编排框架：将一系列修复步骤组织成一个有序流水线，
依次执行并汇总统计信息。具体的修复步骤定义在 ``fixes`` 中，本模块仅
负责调度与统计合并，不包含任何业务逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session


@dataclass
class FixStep:
    """单个修复步骤的描述与执行函数。

    Attributes:
        name: 步骤的唯一标识名（如 ``"fix_options_and_labels"``）。
        description: 步骤的人类可读说明，用于日志/调试。
        fn: 步骤执行函数，签名为 ``fn(db: Session) -> dict``，返回该步骤
            贡献的统计信息子字典，将被合并进流水线的最终统计字典。
    """

    name: str
    description: str
    fn: Callable[[Session], dict]


@dataclass
class FixPipeline:
    """有序修复步骤流水线。

    通过 ``add_step`` 依次注册步骤，``run`` 按注册顺序执行每个步骤，
    并将各步骤返回的统计字典合并为一个总的统计字典返回。

    Attributes:
        steps: 已注册的修复步骤列表（按注册顺序）。
    """

    steps: list[FixStep] = field(default_factory=list)

    def add_step(self, step: FixStep) -> "FixPipeline":
        """向流水线追加一个修复步骤。

        Args:
            step: 要追加的 :class:`FixStep`。

        Returns:
            返回流水线自身，便于链式调用。
        """
        self.steps.append(step)
        return self

    def run(self, db: Session) -> dict:
        """按注册顺序执行所有修复步骤，返回汇总的统计字典。

        每个步骤的执行函数返回一个统计子字典，本方法按顺序将其合并
        （后注册步骤的同名字段会覆盖先注册步骤的，但实际各步骤使用
        不同的字段名）。合并后的字典即为最终的修复统计信息。

        Args:
            db: 数据库会话。

        Returns:
            汇总后的统计字典。
        """
        stats: dict = {}
        for step in self.steps:
            result = step.fn(db)
            if result:
                stats.update(result)
        return stats
