"""
阶段6 单元测试：会计分录判错引擎。

测试范围：
- 借贷平衡校验
- 有借有贷校验
- 金额校验（零、负数）
- 科目合法性校验
- 重复科目检测
- 空分录检测
- 方向正确性
- 标准科目表查询
- 自定义科目
- 备抵科目
- 分录解释生成
- 修正建议
- 多行复杂分录
- 精度处理
"""
import pytest

from app.engines.journal_validator import (
    AccountType,
    EntryDirection,
    ErrorType,
    JournalEntryLine,
    JournalEntryValidator,
    STANDARD_ACCOUNTS,
    ValidationResult,
)


def make_line(account: str, direction: str, amount: float) -> JournalEntryLine:
    """创建分录行的辅助函数。"""
    return JournalEntryLine(account=account, direction=direction, amount=amount)


@pytest.mark.unit
class TestValidEntries:
    """测试正确分录。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_simple_valid_entry(self):
        """简单借贷平衡分录应通过。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("主营业务收入", "贷", 10000),
        ]
        result = self.validator.validate(lines)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.total_debit == 10000
        assert result.total_credit == 10000
        assert result.balance_diff == 0

    def test_multi_line_valid_entry(self):
        """多行分录（一借多贷）应通过。"""
        lines = [
            make_line("银行存款", "借", 11700),
            make_line("主营业务收入", "贷", 10000),
            make_line("应交税费", "贷", 1700),
        ]
        result = self.validator.validate(lines)

        assert result.is_valid
        assert result.total_debit == 11700
        assert result.total_credit == 11700

    def test_multi_debit_multi_credit(self):
        """多借多贷分录应通过。"""
        lines = [
            make_line("管理费用", "借", 5000),
            make_line("销售费用", "借", 3000),
            make_line("银行存款", "贷", 6000),
            make_line("库存现金", "贷", 2000),
        ]
        result = self.validator.validate(lines)

        assert result.is_valid
        assert result.total_debit == 8000
        assert result.total_credit == 8000

    def test_purchase_entry(self):
        """购入原材料分录应通过。"""
        lines = [
            make_line("原材料", "借", 10000),
            make_line("应交税费", "借", 1300),
            make_line("应付账款", "贷", 11300),
        ]
        result = self.validator.validate(lines)
        assert result.is_valid


@pytest.mark.unit
class TestUnbalancedEntries:
    """测试借贷不平衡。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_debit_greater(self):
        """借方大于贷方应报错。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("主营业务收入", "贷", 9000),
        ]
        result = self.validator.validate(lines)

        assert not result.is_valid
        assert any(e.error_type == ErrorType.UNBALANCED for e in result.errors)
        assert result.balance_diff == 1000

    def test_credit_greater(self):
        """贷方大于借方应报错。"""
        lines = [
            make_line("银行存款", "借", 8000),
            make_line("主营业务收入", "贷", 10000),
        ]
        result = self.validator.validate(lines)

        assert not result.is_valid
        assert result.balance_diff == -2000

    def test_balance_diff_precision(self):
        """差额应正确处理浮点精度。"""
        lines = [
            make_line("银行存款", "借", 100.10),
            make_line("主营业务收入", "贷", 100.11),
        ]
        result = self.validator.validate(lines)

        # 差额 0.01 应被检测到
        assert not result.is_valid
        assert abs(result.balance_diff - (-0.01)) < 0.001


@pytest.mark.unit
class TestMissingDirection:
    """测试缺少借方或贷方。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_only_debit(self):
        """只有借方应报错。"""
        lines = [make_line("银行存款", "借", 10000)]
        result = self.validator.validate(lines)

        assert not result.is_valid
        assert any(e.error_type == ErrorType.MISSING_DIRECTION for e in result.errors)

    def test_only_credit(self):
        """只有贷方应报错。"""
        lines = [make_line("主营业务收入", "贷", 10000)]
        result = self.validator.validate(lines)

        assert not result.is_valid
        assert any(e.error_type == ErrorType.MISSING_DIRECTION for e in result.errors)


@pytest.mark.unit
class TestAmountValidation:
    """测试金额校验。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_zero_amount(self):
        """金额为零应报错。"""
        lines = [
            make_line("银行存款", "借", 0),
            make_line("主营业务收入", "贷", 0),
        ]
        result = self.validator.validate(lines)

        assert not result.is_valid
        zero_errors = [e for e in result.errors if e.error_type == ErrorType.ZERO_AMOUNT]
        assert len(zero_errors) == 2  # 两行都为零

    def test_negative_amount(self):
        """金额为负应报错。"""
        lines = [
            make_line("银行存款", "借", -10000),
            make_line("主营业务收入", "贷", -10000),
        ]
        result = self.validator.validate(lines)

        assert not result.is_valid
        neg_errors = [e for e in result.errors if e.error_type == ErrorType.NEGATIVE_AMOUNT]
        assert len(neg_errors) == 2

    def test_mixed_valid_invalid_amount(self):
        """混合有效和无效金额应只报无效的。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("主营业务收入", "贷", 0),
        ]
        result = self.validator.validate(lines)

        zero_errors = [e for e in result.errors if e.error_type == ErrorType.ZERO_AMOUNT]
        assert len(zero_errors) == 1
        assert zero_errors[0].account == "主营业务收入"


@pytest.mark.unit
class TestAccountValidation:
    """测试科目合法性。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_unknown_account(self):
        """未知科目应报错。"""
        lines = [
            make_line("不存在的科目", "借", 10000),
            make_line("主营业务收入", "贷", 10000),
        ]
        result = self.validator.validate(lines)

        assert not result.is_valid
        unknown = [e for e in result.errors if e.error_type == ErrorType.UNKNOWN_ACCOUNT]
        assert len(unknown) == 1
        assert unknown[0].account == "不存在的科目"

    def test_standard_account_lookup(self):
        """标准科目应能查到类别。"""
        assert self.validator.get_account_type("银行存款") == AccountType.ASSET
        assert self.validator.get_account_type("应付账款") == AccountType.LIABILITY
        assert self.validator.get_account_type("实收资本") == AccountType.EQUITY
        assert self.validator.get_account_type("主营业务收入") == AccountType.REVENUE
        assert self.validator.get_account_type("管理费用") == AccountType.EXPENSE

    def test_custom_account(self):
        """自定义科目应被识别。"""
        validator = JournalEntryValidator(custom_accounts={
            "研发支出": AccountType.EXPENSE,
        })
        lines = [
            make_line("研发支出", "借", 50000),
            make_line("银行存款", "贷", 50000),
        ]
        result = validator.validate(lines)
        assert result.is_valid

    def test_account_type_assigned(self):
        """验证后应自动填充科目类别。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("主营业务收入", "贷", 10000),
        ]
        self.validator.validate(lines)

        assert lines[0].account_type == AccountType.ASSET
        assert lines[1].account_type == AccountType.REVENUE


@pytest.mark.unit
class TestDuplicateAccount:
    """测试重复科目。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_duplicate_same_direction(self):
        """同一科目同方向重复应报错。"""
        lines = [
            make_line("银行存款", "借", 5000),
            make_line("银行存款", "借", 5000),
            make_line("主营业务收入", "贷", 10000),
        ]
        result = self.validator.validate(lines)

        dup_errors = [e for e in result.errors if e.error_type == ErrorType.DUPLICATE_ACCOUNT]
        assert len(dup_errors) == 1

    def test_same_account_different_direction_ok(self):
        """同一科目不同方向不应报错。"""
        lines = [
            make_line("应收账款", "借", 5000),
            make_line("应收账款", "贷", 3000),
            make_line("银行存款", "借", 3000),
        ]
        # 借方：应收 5000 + 银行 3000 = 8000
        # 贷方：应收 3000 → 不平衡
        # 但不应有 DUPLICATE_ACCOUNT 错误
        result = self.validator.validate(lines)
        dup_errors = [e for e in result.errors if e.error_type == ErrorType.DUPLICATE_ACCOUNT]
        assert len(dup_errors) == 0


@pytest.mark.unit
class TestEmptyEntry:
    """测试空分录。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_empty_lines(self):
        """空列表应报错。"""
        result = self.validator.validate([])

        assert not result.is_valid
        assert any(e.error_type == ErrorType.EMPTY_ENTRY for e in result.errors)


@pytest.mark.unit
class TestMultipleErrors:
    """测试多重错误同时出现。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_collects_all_errors(self):
        """应收集所有错误而非遇到第一个就停止。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("未知科目", "借", -5000),
            make_line("主营业务收入", "贷", 8000),
        ]
        result = self.validator.validate(lines)

        assert not result.is_valid
        # 应有：未知科目、负金额、借贷不平衡
        error_types = {e.error_type for e in result.errors}
        assert ErrorType.UNKNOWN_ACCOUNT in error_types
        assert ErrorType.NEGATIVE_AMOUNT in error_types
        assert ErrorType.UNBALANCED in error_types


@pytest.mark.unit
class TestExplanation:
    """测试分录解释生成。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_explain_valid_entry(self):
        """正确分录的解释应包含平衡信息。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("主营业务收入", "贷", 10000),
        ]
        explanation = self.validator.explain_entry(lines)

        assert "借方合计" in explanation
        assert "贷方合计" in explanation
        assert "平衡" in explanation
        assert "银行存款" in explanation
        assert "资产" in explanation

    def test_explain_empty(self):
        """空分录应返回提示。"""
        explanation = self.validator.explain_entry([])
        assert "空" in explanation

    def test_explain_shows_account_type(self):
        """解释应显示科目类别。"""
        lines = [
            make_line("管理费用", "借", 5000),
            make_line("银行存款", "贷", 5000),
        ]
        explanation = self.validator.explain_entry(lines)
        assert "费用" in explanation
        assert "资产" in explanation


@pytest.mark.unit
class TestCorrectionSuggestion:
    """测试修正建议。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_suggest_for_unbalanced(self):
        """不平衡错误应有修正建议。"""
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("主营业务收入", "贷", 9000),
        ]
        result = self.validator.validate(lines)
        unbalanced_error = [e for e in result.errors if e.error_type == ErrorType.UNBALANCED][0]

        suggestion = self.validator.suggest_correction(lines, unbalanced_error)
        assert suggestion is not None
        assert "借贷" in suggestion or "金额" in suggestion

    def test_suggest_for_unknown_account(self):
        """未知科目错误应有修正建议。"""
        lines = [
            make_line("未知科目", "借", 10000),
            make_line("主营业务收入", "贷", 10000),
        ]
        result = self.validator.validate(lines)
        unknown_error = [e for e in result.errors if e.error_type == ErrorType.UNKNOWN_ACCOUNT][0]

        suggestion = self.validator.suggest_correction(lines, unknown_error)
        assert suggestion is not None
        assert "未知科目" in suggestion or "科目名称" in suggestion

    def test_suggest_for_negative_amount(self):
        """负金额错误应有修正建议。"""
        lines = [
            make_line("银行存款", "借", -10000),
            make_line("主营业务收入", "贷", -10000),
        ]
        result = self.validator.validate(lines)
        neg_error = [e for e in result.errors if e.error_type == ErrorType.NEGATIVE_AMOUNT][0]

        suggestion = self.validator.suggest_correction(lines, neg_error)
        assert suggestion is not None
        assert "负数" in suggestion or "相反方向" in suggestion


@pytest.mark.unit
class TestCPASpecificScenarios:
    """测试 CPA 考试常见分录场景。"""

    def setup_method(self):
        self.validator = JournalEntryValidator()

    def test_depreciation_entry(self):
        """计提折旧分录（备抵科目）。"""
        lines = [
            make_line("管理费用", "借", 5000),
            make_line("累计折旧", "贷", 5000),
        ]
        result = self.validator.validate(lines)
        assert result.is_valid

    def test_salary_payment(self):
        """发放工资分录。"""
        lines = [
            make_line("应付职工薪酬", "借", 50000),
            make_line("银行存款", "贷", 50000),
        ]
        result = self.validator.validate(lines)
        assert result.is_valid

    def tax_payment(self):
        """缴纳税费分录。"""
        lines = [
            make_line("应交税费", "借", 1700),
            make_line("银行存款", "贷", 1700),
        ]
        result = self.validator.validate(lines)
        assert result.is_valid

    def test_complex_purchase_with_tax(self):
        """复杂采购分录（含增值税）。"""
        lines = [
            make_line("原材料", "借", 100000),
            make_line("应交税费", "借", 13000),
            make_line("银行存款", "贷", 113000),
        ]
        result = self.validator.validate(lines)
        assert result.is_valid

    def test_common_student_error_wrong_direction(self):
        """学生常见错误：偿还借款方向反了。"""
        # 错误：借银行存款贷短期借款（这是借款的分录，不是偿还）
        lines = [
            make_line("银行存款", "借", 10000),
            make_line("短期借款", "贷", 10000),
        ]
        result = self.validator.validate(lines)
        # 虽然借贷平衡，但方向可能有误（这是借款而非偿还）
        # 引擎应通过（方向启发式检查暂不强制报错）
        assert result.is_valid  # 平衡检查通过

    def test_student_error_unbalanced(self):
        """学生常见错误：金额不等。"""
        lines = [
            make_line("固定资产", "借", 50000),
            make_line("银行存款", "贷", 45000),
        ]
        result = self.validator.validate(lines)
        assert not result.is_valid
        assert result.balance_diff == 5000
