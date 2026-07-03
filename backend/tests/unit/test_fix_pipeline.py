"""
题库修复管道单元测试。

验证规范：
- FixPipeline 按序执行步骤
- FixStep dataclass 结构正确
- fix_existing_database 返回完整统计字典
- text_utils 工具函数行为正确
"""
import pytest

from app.question_data.pipeline import FixPipeline, FixStep
from app.question_data.text_utils import (
    extract_first_sentence,
    extract_key_numbers,
    extract_formula_and_result,
    is_calculation,
    question_type_desc,
    strip_dedup_suffixes,
)


class TestFixPipeline:
    """管道框架验证。"""

    def test_fix_step_dataclass(self):
        step = FixStep(name="test", description="测试步骤", fn=lambda db: 0)
        assert step.name == "test"
        assert step.description == "测试步骤"

    def test_pipeline_runs_steps_in_order(self):
        order: list[str] = []
        pipeline = FixPipeline()
        pipeline.add_step(FixStep("step1", "第一步", lambda db: order.append("1") or {}))
        pipeline.add_step(FixStep("step2", "第二步", lambda db: order.append("2") or {}))
        pipeline.add_step(FixStep("step3", "第三步", lambda db: order.append("3") or {}))
        pipeline.run(None)
        assert order == ["1", "2", "3"]

    def test_pipeline_collects_stats(self):
        pipeline = FixPipeline()
        pipeline.add_step(FixStep("shuffle", "打乱", lambda db: {"shuffled": 10}))
        pipeline.add_step(FixStep("fix", "修复", lambda db: {"fixed": 5}))
        stats = pipeline.run(None)
        assert stats["shuffled"] == 10
        assert stats["fixed"] == 5

    def test_pipeline_empty(self):
        pipeline = FixPipeline()
        stats = pipeline.run(None)
        assert stats == {}


class TestTextUtils:
    """文本工具函数验证。"""

    def test_strip_dedup_suffixes(self):
        assert strip_dedup_suffixes("选项A（错误）") == "选项A"
        assert strip_dedup_suffixes("正常文本") == "正常文本"

    def test_extract_first_sentence(self):
        text = "第一句话。第二句话。"
        result = extract_first_sentence(text)
        assert "第一句话" in result

    def test_extract_key_numbers(self):
        text = "买价200万元，运费8万元"
        result = extract_key_numbers(text)
        assert "200" in result or "200万元" in result

    def test_extract_formula_and_result(self):
        text = "200+8+2=210"
        formula, result = extract_formula_and_result(text)
        assert formula is not None
        assert result is not None

    def test_is_calculation_with_formula(self):
        from app.models import Question
        q = Question(content="计算结果", explanation="入账价值=买价+运费=200+8=208万元", question_type="single_choice")
        assert is_calculation(q) is True

    def test_is_calculation_without_formula(self):
        from app.models import Question
        q = Question(content="以下说法是否正确", explanation="该说法正确。根据会计准则规定。", question_type="judgment")
        assert is_calculation(q) is False

    def test_question_type_desc(self):
        assert question_type_desc("single_choice") is not None
        assert question_type_desc("judgment") is not None
        assert question_type_desc("multiple_choice") is not None
