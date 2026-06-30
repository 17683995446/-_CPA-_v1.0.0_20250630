"""
AI 出题引擎。

第一性原理：好的题目应该精准匹配学习者的当前水平，
在知识点的不同维度上考查理解深度。

本引擎采用「模板 + 变体」策略：
- 模板定义题目骨架和可变插槽
- 变体通过替换插槽生成不同但同构的题目
- 难度通过调整干扰项和考查深度来控制

设计原则：
- 模板可扩展（未来接入 LLM 生成新模板）
- 变体可控（确保同构性，避免无意义的重复）
- 知识点关联（每道题明确关联考查的知识点）

业务规范：
- CPA 题型：单选、多选、判断、综合题（TBS）、会计分录题
- 题目应覆盖知识点的不同认知层次（记忆→理解→应用→分析）
"""
import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class QuestionType(str, Enum):
    """题目类型。"""
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    JUDGMENT = "judgment"
    TBS = "tbs"
    JOURNAL_ENTRY = "journal_entry"


class CognitiveLevel(str, Enum):
    """认知层次（布鲁姆分类法）。"""
    REMEMBER = "remember"      # 记忆
    UNDERSTAND = "understand"  # 理解
    APPLY = "apply"            # 应用
    ANALYZE = "analyze"        # 分析


@dataclass
class QuestionOptionData:
    """题目选项数据。"""
    label: str
    content: str
    is_correct: bool


@dataclass
class GeneratedQuestion:
    """生成的题目。"""
    question_type: QuestionType
    content: str
    answer: str
    explanation: str
    difficulty: int
    options: list[QuestionOptionData] = field(default_factory=list)
    knowledge_point_code: Optional[str] = None
    cognitive_level: CognitiveLevel = CognitiveLevel.UNDERSTAND
    source: str = "ai_generated"
    variant_id: str = ""  # 变体标识，用于追踪同源题目

    def __post_init__(self):
        if not self.variant_id:
            self.variant_id = uuid.uuid4().hex[:8]


@dataclass
class QuestionTemplate:
    """
    题目模板。

    slots: 可变插槽，每个插槽有多个候选值
    compute_fn: 可选，从原始插槽值计算派生值的函数 (dict) -> dict
    correct_answer: 正确答案模板
    distractors: 干扰项模板列表
    """
    template_id: str
    knowledge_point_code: str
    subject: str
    question_type: QuestionType
    cognitive_level: CognitiveLevel
    content_template: str  # 使用 {slot_name} 作为占位符
    answer_template: str
    explanation_template: str
    slots: dict[str, list] = field(default_factory=dict)
    distractor_templates: list[str] = field(default_factory=list)
    base_difficulty: int = 3
    compute_fn: Optional[callable] = None  # (slot_values) -> dict of computed values


class QuestionGenerator:
    """
    出题引擎。

    核心方法：
    - generate(template, difficulty): 根据模板和难度生成题目
    - generate_variants(template, count): 生成多个变体
    - generate_by_knowledge_point(kp_code, difficulty): 按知识点出题
    - generate_error_variant(question): 基于错题生成变体
    """

    def __init__(self):
        self.templates: dict[str, QuestionTemplate] = {}
        self._register_default_templates()

    def register_template(self, template: QuestionTemplate) -> None:
        """注册题目模板。"""
        self.templates[template.template_id] = template

    def generate(
        self,
        template: QuestionTemplate,
        difficulty: int = 3,
        rng: Optional[random.Random] = None,
    ) -> GeneratedQuestion:
        """
        根据模板生成一道题目。

        参数：
        - template: 题目模板
        - difficulty: 目标难度 1-5
        - rng: 随机数生成器（用于测试可复现性）

        返回：GeneratedQuestion
        """
        rng = rng or random.Random()

        # 填充插槽
        slot_values = {}
        for slot_name, candidates in template.slots.items():
            slot_values[slot_name] = rng.choice(candidates)

        # 计算派生值（如需要）
        all_values = dict(slot_values)
        if template.compute_fn:
            all_values.update(template.compute_fn(slot_values))

        # 渲染题干和答案
        content = template.content_template.format(**all_values)
        answer = template.answer_template.format(**all_values)
        explanation = template.explanation_template.format(**all_values)

        # 生成选项
        options = self._generate_options(template, all_values, difficulty, rng)

        # 根据难度调整
        adjusted_difficulty = max(1, min(5, difficulty))

        return GeneratedQuestion(
            question_type=template.question_type,
            content=content,
            answer=answer,
            explanation=explanation,
            difficulty=adjusted_difficulty,
            options=options,
            knowledge_point_code=template.knowledge_point_code,
            cognitive_level=template.cognitive_level,
        )

    def generate_variants(
        self,
        template: QuestionTemplate,
        count: int = 3,
        difficulty: int = 3,
        rng: Optional[random.Random] = None,
    ) -> list[GeneratedQuestion]:
        """
        生成同一模板的多个变体。

        变体之间通过不同的插槽值产生差异，但考查的知识点相同。
        """
        rng = rng or random.Random()
        variants = []
        seen_contents: set[str] = set()

        attempts = 0
        max_attempts = count * 5  # 防止无限循环

        while len(variants) < count and attempts < max_attempts:
            attempts += 1
            question = self.generate(template, difficulty, rng)
            if question.content not in seen_contents:
                seen_contents.add(question.content)
                variants.append(question)

        return variants

    def generate_by_knowledge_point(
        self,
        kp_code: str,
        difficulty: int = 3,
        rng: Optional[random.Random] = None,
    ) -> Optional[GeneratedQuestion]:
        """按知识点代码出题：查找匹配模板并生成。"""
        matching = [
            t for t in self.templates.values()
            if t.knowledge_point_code == kp_code
        ]
        if not matching:
            return None

        rng = rng or random.Random()
        template = rng.choice(matching)
        return self.generate(template, difficulty, rng)

    def generate_error_variant(
        self,
        original: GeneratedQuestion,
        rng: Optional[random.Random] = None,
    ) -> GeneratedQuestion:
        """
        基于错题生成变体。

        策略：保持题目结构不变，替换插槽值生成新的变体。
        用于错题强化练习，帮助用户从不同角度理解同一知识点。
        """
        rng = rng or random.Random()

        # 查找原始题目的模板
        template = None
        for t in self.templates.values():
            if t.knowledge_point_code == original.knowledge_point_code:
                template = t
                break

        if template:
            # 用模板生成新变体
            variant = self.generate(template, original.difficulty, rng)
            variant.variant_id = f"err_{original.variant_id}"
            return variant
        else:
            # 无模板时，简单调整选项顺序
            shuffled_options = original.options.copy()
            rng.shuffle(shuffled_options)
            return GeneratedQuestion(
                question_type=original.question_type,
                content=original.content,
                answer=original.answer,
                explanation=original.explanation,
                difficulty=original.difficulty,
                options=shuffled_options,
                knowledge_point_code=original.knowledge_point_code,
                cognitive_level=original.cognitive_level,
                variant_id=f"err_{original.variant_id}",
            )

    def _generate_options(
        self,
        template: QuestionTemplate,
        slot_values: dict,
        difficulty: int,
        rng: random.Random,
    ) -> list[QuestionOptionData]:
        """生成选项（含正确答案和干扰项）。"""
        if template.question_type == QuestionType.JUDGMENT:
            answer = template.answer_template.format(**slot_values)
            is_correct_true = answer.lower() in ("正确", "对", "true", "t", "yes")
            return [
                QuestionOptionData("A", "正确", is_correct_true),
                QuestionOptionData("B", "错误", not is_correct_true),
            ]

        # 选择题：生成正确答案 + 干扰项
        correct_answer = template.answer_template.format(**slot_values)
        options = [QuestionOptionData("A", correct_answer, True)]

        # 根据难度决定干扰项数量
        num_distractors = min(3, max(1, difficulty))
        available_distractors = template.distractor_templates[:]

        rng.shuffle(available_distractors)
        selected = available_distractors[:num_distractors]

        labels = ["B", "C", "D", "E"]
        for i, distractor_tmpl in enumerate(selected):
            distractor = distractor_tmpl.format(**slot_values)
            options.append(QuestionOptionData(labels[i], distractor, False))

        # 打乱选项顺序（但保持 is_correct 标记）
        rng.shuffle(options)
        # 重新分配标签
        for i, opt in enumerate(options):
            opt.label = chr(65 + i)  # A, B, C, D...

        return options

    # ========== 默认模板注册 ==========

    def _register_default_templates(self) -> None:
        """注册 CPA 默认题目模板。"""

        # --- 会计：借贷记账法 ---
        self.register_template(QuestionTemplate(
            template_id="acc_journal_basics_01",
            knowledge_point_code="ACC-01-01",
            subject="会计",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.UNDERSTAND,
            content_template="企业用银行存款偿还短期借款{amount}万元，下列会计处理正确的是（　）。",
            answer_template="借：短期借款 {amount}万元；贷：银行存款 {amount}万元",
            explanation_template="偿还短期借款时，资产（银行存款）减少记贷方，负债（短期借款）减少记借方。",
            slots={"amount": ["10", "20", "50", "100", "200"]},
            distractor_templates=[
                "借：银行存款 {amount}万元；贷：短期借款 {amount}万元",
                "借：短期借款 {amount}万元；贷：应付账款 {amount}万元",
                "借：长期借款 {amount}万元；贷：银行存款 {amount}万元",
            ],
            base_difficulty=2,
        ))

        # --- 会计：存货初始计量 ---
        def _inventory_compute(v):
            total = v["price"] + v["freight"] + v["sort"]
            return {
                "total": total,
                "price_plus_tax": v["price"] + v["tax"],
                "price_only": v["price"],
                "all_included": v["price"] + v["tax"] + v["freight"] + v["sort"],
            }

        self.register_template(QuestionTemplate(
            template_id="acc_inventory_01",
            knowledge_point_code="ACC-03-01",
            subject="会计",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.APPLY,
            content_template="某企业购入原材料一批，买价{price}万元，增值税进项税额{tax}万元，运输费{freight}万元，入库前挑选整理费{sort}万元。该批材料的入账价值为（　）万元。",
            answer_template="{total}",
            explanation_template="存货的入账价值包括买价、运输费、入库前挑选整理费等采购成本，不包括增值税进项税额。入账价值 = {price} + {freight} + {sort} = {total}万元。",
            slots={
                "price": [100, 200, 150, 80],
                "tax": [13, 26, 19.5, 10.4],
                "freight": [5, 8, 3, 10],
                "sort": [2, 1, 3, 5],
            },
            distractor_templates=[
                "{price_plus_tax}",  # 含税错误
                "{price_only}",      # 仅买价
                "{all_included}",    # 全部包含
            ],
            base_difficulty=3,
            compute_fn=_inventory_compute,
        ))

        # --- 审计：审计证据 ---
        self.register_template(QuestionTemplate(
            template_id="aud_evidence_01",
            knowledge_point_code="AUD-02-01",
            subject="审计",
            question_type=QuestionType.JUDGMENT,
            cognitive_level=CognitiveLevel.UNDERSTAND,
            content_template="审计证据的充分性是对审计证据数量的衡量，适当性是对审计证据质量的衡量。（　）",
            answer_template="正确",
            explanation_template="充分性是指审计证据的数量，适当性是指审计证据的相关性和可靠性（质量）。这是审计准则的基本概念。",
            slots={},
            distractor_templates=[],
            base_difficulty=2,
        ))

        # --- 税法：增值税 ---
        def _vat_compute(v):
            output_tax = v["revenue"] * v["rate"] / 100
            return {
                "output_tax": output_tax,
                "input_tax_wrong": round(output_tax * 0.7, 1),
                "tax_inclusive": round(v["revenue"] * (1 + v["rate"] / 100), 1),
            }

        self.register_template(QuestionTemplate(
            template_id="tax_vat_01",
            knowledge_point_code="TAX-01-01",
            subject="税法",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.APPLY,
            content_template="某一般纳税人企业{month}月销售货物取得不含税销售额{revenue}万元，适用税率{rate}%。该企业当月增值税销项税额为（　）万元。",
            answer_template="{output_tax}",
            explanation_template="销项税额 = 不含税销售额 × 适用税率 = {revenue} × {rate}% = {output_tax}万元。",
            slots={
                "month": ["1", "3", "6", "9", "12"],
                "revenue": [100, 200, 500, 1000],
                "rate": [13, 9, 6],
            },
            distractor_templates=[
                "{input_tax_wrong}",   # 用进项税额混淆
                "{revenue}",           # 忘记乘税率
                "{tax_inclusive}",     # 用含税销售额
            ],
            base_difficulty=3,
            compute_fn=_vat_compute,
        ))

        # --- 经济法：公司法 ---
        self.register_template(QuestionTemplate(
            template_id="law_company_01",
            knowledge_point_code="LAW-01-01",
            subject="经济法",
            question_type=QuestionType.SINGLE_CHOICE,
            cognitive_level=CognitiveLevel.REMEMBER,
            content_template="根据《公司法》，有限责任公司的股东人数上限为（　）人。",
            answer_template="50",
            explanation_template="《公司法》规定，有限责任公司由50个以下股东出资设立。",
            slots={},
            distractor_templates=["30", "100", "200"],
            base_difficulty=1,
        ))

    def list_templates(self) -> list[str]:
        """列出所有已注册的模板 ID。"""
        return list(self.templates.keys())

    def get_template(self, template_id: str) -> Optional[QuestionTemplate]:
        """获取指定模板。"""
        return self.templates.get(template_id)
