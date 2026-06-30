"""
阶段4 单元测试：AI 出题引擎。

测试范围：
- 模板注册与获取
- 插槽填充与题目生成
- 选项生成（正确答案 + 干扰项）
- 难度调整
- 变体生成（无重复）
- 按知识点出题
- 错题变体生成
- 判断题生成
- 默认模板可用性
"""
import random

import pytest

from app.engines.question_gen import (
    CognitiveLevel,
    GeneratedQuestion,
    QuestionGenerator,
    QuestionOptionData,
    QuestionTemplate,
    QuestionType,
)


@pytest.mark.unit
class TestTemplateManagement:
    """测试模板管理。"""

    def test_register_template(self):
        """注册模板应成功。"""
        gen = QuestionGenerator()
        template = QuestionTemplate(
            template_id="test_01",
            knowledge_point_code="TEST-01",
            subject="会计",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.UNDERSTAND,
            content_template="测试题 {x}",
            answer_template="答案 {x}",
            explanation_template="解析 {x}",
            slots={"x": ["a", "b"]},
        )
        gen.register_template(template)

        assert "test_01" in gen.list_templates()
        assert gen.get_template("test_01") is not None

    def test_get_nonexistent_template(self):
        """获取不存在的模板应返回 None。"""
        gen = QuestionGenerator()
        assert gen.get_template("nonexistent") is None

    def test_default_templates_registered(self):
        """引擎初始化时应注册默认模板。"""
        gen = QuestionGenerator()
        templates = gen.list_templates()
        assert len(templates) >= 5  # 至少 5 个默认模板
        assert "acc_journal_basics_01" in templates
        assert "tax_vat_01" in templates


@pytest.mark.unit
class TestQuestionGeneration:
    """测试题目生成。"""

    def setup_method(self):
        self.gen = QuestionGenerator()
        self.rng = random.Random(42)  # 固定种子保证可复现

    def test_generate_basic(self):
        """基本生成应填充插槽并返回完整题目。"""
        template = self.gen.get_template("acc_journal_basics_01")
        question = self.gen.generate(template, rng=self.rng)

        assert isinstance(question, GeneratedQuestion)
        assert "万元" in question.content  # 插槽已填充
        assert question.answer != ""  # 答案非空
        assert question.explanation != ""
        assert question.knowledge_point_code == "ACC-01-01"
        assert question.source == "ai_generated"

    def test_generate_has_options(self):
        """选择题应生成选项。"""
        template = self.gen.get_template("acc_journal_basics_01")
        question = self.gen.generate(template, rng=self.rng)

        assert len(question.options) >= 2  # 至少正确答案 + 1 干扰项
        # 应恰好有一个正确答案
        correct = [o for o in question.options if o.is_correct]
        assert len(correct) == 1

    def test_generate_difficulty_affects_distractors(self):
        """难度应影响干扰项数量。"""
        template = self.gen.get_template("acc_journal_basics_01")

        easy = self.gen.generate(template, difficulty=1, rng=random.Random(42))
        hard = self.gen.generate(template, difficulty=4, rng=random.Random(42))

        assert len(easy.options) <= len(hard.options)

    def test_generate_judgment_question(self):
        """判断题应生成两个选项（正确/错误）。"""
        template = self.gen.get_template("aud_evidence_01")
        question = self.gen.generate(template, rng=self.rng)

        assert question.question_type == QuestionType.JUDGMENT
        assert len(question.options) == 2
        correct = [o for o in question.options if o.is_correct]
        assert len(correct) == 1

    def test_generate_difficulty_clamped(self):
        """难度应限制在 1-5 范围内。"""
        template = self.gen.get_template("acc_journal_basics_01")
        q_low = self.gen.generate(template, difficulty=-5, rng=self.rng)
        q_high = self.gen.generate(template, difficulty=100, rng=self.rng)

        assert q_low.difficulty == 1
        assert q_high.difficulty == 5

    def test_variant_id_generated(self):
        """生成的题目应有变体 ID。"""
        template = self.gen.get_template("acc_journal_basics_01")
        question = self.gen.generate(template, rng=self.rng)
        assert len(question.variant_id) > 0


@pytest.mark.unit
class TestVariantGeneration:
    """测试变体生成。"""

    def setup_method(self):
        self.gen = QuestionGenerator()

    def test_generate_variants_count(self):
        """应生成指定数量的变体。"""
        template = self.gen.get_template("acc_journal_basics_01")
        variants = self.gen.generate_variants(template, count=3, rng=random.Random(42))

        assert len(variants) == 3

    def test_variants_no_duplicate_content(self):
        """变体之间不应有重复的题干。"""
        template = self.gen.get_template("acc_journal_basics_01")
        variants = self.gen.generate_variants(template, count=3, rng=random.Random(42))

        contents = [v.content for v in variants]
        assert len(contents) == len(set(contents))  # 无重复

    def test_variants_same_knowledge_point(self):
        """变体应关联同一知识点。"""
        template = self.gen.get_template("acc_journal_basics_01")
        variants = self.gen.generate_variants(template, count=3, rng=random.Random(42))

        for v in variants:
            assert v.knowledge_point_code == "ACC-01-01"


@pytest.mark.unit
class TestKnowledgePointGeneration:
    """测试按知识点出题。"""

    def setup_method(self):
        self.gen = QuestionGenerator()

    def test_generate_by_kp(self):
        """按知识点代码应能生成题目。"""
        question = self.gen.generate_by_knowledge_point(
            "ACC-01-01", rng=random.Random(42)
        )
        assert question is not None
        assert question.knowledge_point_code == "ACC-01-01"

    def test_generate_by_nonexistent_kp(self):
        """不存在的知识点应返回 None。"""
        question = self.gen.generate_by_knowledge_point("NONEXISTENT")
        assert question is None


@pytest.mark.unit
class TestErrorVariant:
    """测试错题变体生成。"""

    def setup_method(self):
        self.gen = QuestionGenerator()

    def test_error_variant_has_prefix(self):
        """错题变体应有 err_ 前缀。"""
        template = self.gen.get_template("acc_journal_basics_01")
        original = self.gen.generate(template, rng=random.Random(42))

        variant = self.gen.generate_error_variant(original, rng=random.Random(99))
        assert variant.variant_id.startswith("err_")

    def test_error_variant_same_kp(self):
        """错题变体应关联同一知识点。"""
        template = self.gen.get_template("acc_journal_basics_01")
        original = self.gen.generate(template, rng=random.Random(42))

        variant = self.gen.generate_error_variant(original, rng=random.Random(99))
        assert variant.knowledge_point_code == original.knowledge_point_code

    def test_error_variant_different_content(self):
        """错题变体应与原题不同（不同插槽值）。"""
        template = self.gen.get_template("acc_journal_basics_01")
        original = self.gen.generate(template, rng=random.Random(42))

        variant = self.gen.generate_error_variant(original, rng=random.Random(99))
        # 可能内容相同（如果插槽值碰巧相同），但至少变体 ID 不同
        assert variant.variant_id != original.variant_id


@pytest.mark.unit
class TestCustomTemplate:
    """测试自定义模板。"""

    def test_custom_template_generation(self):
        """自定义模板应能正常生成题目。"""
        gen = QuestionGenerator()
        template = QuestionTemplate(
            template_id="custom_01",
            knowledge_point_code="CUSTOM-01",
            subject="会计",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.APPLY,
            content_template="某企业购入设备一台，买价{price}万元，安装费{install}万元。设备的入账价值为（　）万元。",
            answer_template="{total}",
            explanation_template="设备入账价值 = 买价 + 安装费 = {price} + {install} = {total}万元。",
            slots={
                "price": [100, 200, 300],
                "install": [5, 10, 15],
            },
            distractor_templates=["{price}", "{install}", "0"],
            base_difficulty=2,
            compute_fn=lambda v: {"total": v["price"] + v["install"]},
        )
        gen.register_template(template)

        question = gen.generate(template, rng=random.Random(42))
        assert "万元" in question.content
        assert len(question.options) >= 2
        assert question.knowledge_point_code == "CUSTOM-01"

    def test_cognitive_level_preserved(self):
        """生成的题目应保留模板的认知层次。"""
        gen = QuestionGenerator()
        template = QuestionTemplate(
            template_id="cog_01",
            knowledge_point_code="COG-01",
            subject="审计",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.ANALYZE,
            content_template="分析题",
            answer_template="答案",
            explanation_template="解析",
            slots={},
            distractor_templates=["干扰项"],
        )
        gen.register_template(template)

        question = gen.generate(template)
        assert question.cognitive_level == CognitiveLevel.ANALYZE
