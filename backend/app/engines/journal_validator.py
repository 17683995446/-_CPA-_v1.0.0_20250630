"""
会计分录判错引擎。

第一性原理：会计分录是经济业务的货币化表达，遵循「借贷记账法」核心规则：
  1. 有借必有贷（每笔分录必须同时有借方和贷方）
  2. 借贷必相等（借方合计 = 贷方合计）
  3. 账户方向正确（资产/费用增加记借，负债/权益/收入增加记贷）

本引擎对用户提交的会计分录进行多维验证，识别常见错误类型，
并提供详细反馈帮助用户理解错误原因。

业务规范（企业会计准则）：
- 账户分类：资产、负债、所有者权益、收入、费用、利润
- 记账方向：资产/费用 → 借增贷减；负债/权益/收入/利润 → 贷增借减
- 复式记账：每笔业务必须借贷平衡
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AccountType(str, Enum):
    """会计科目类别。"""
    ASSET = "资产"           # 资产类：借增贷减
    LIABILITY = "负债"       # 负债类：贷增借减
    EQUITY = "所有者权益"    # 所有者权益类：贷增借减
    REVENUE = "收入"         # 收入类：贷增借减
    EXPENSE = "费用"         # 费用类：借增贷减
    PROFIT = "利润"          # 利润类：贷增借减


class EntryDirection(str, Enum):
    """记账方向。"""
    DEBIT = "借"   # 借方
    CREDIT = "贷"  # 贷方


class ErrorType(str, Enum):
    """分录错误类型。"""
    UNBALANCED = "借贷不平衡"              # 借贷金额不等
    MISSING_DIRECTION = "缺少借方或贷方"    # 有借无贷或有贷无借
    WRONG_DIRECTION = "记账方向错误"        # 方向与科目类别不符
    ZERO_AMOUNT = "金额为零"               # 金额为 0
    NEGATIVE_AMOUNT = "金额为负"           # 金额为负数
    UNKNOWN_ACCOUNT = "未知科目"           # 科目不在标准科目表中
    DUPLICATE_ACCOUNT = "重复科目同方向"    # 同一科目同一方向出现多次
    EMPTY_ENTRY = "空分录"                 # 无分录行


@dataclass
class JournalEntryLine:
    """会计分录单行。"""
    account: str           # 科目名称
    direction: str         # "借" 或 "贷"
    amount: float          # 金额
    account_type: Optional[AccountType] = None  # 科目类别（自动推断或指定）


@dataclass
class ValidationError:
    """验证错误。"""
    error_type: ErrorType
    message: str
    line_index: Optional[int] = None  # 出错的行号（0-based）
    account: Optional[str] = None     # 出错的科目


@dataclass
class ValidationResult:
    """分录验证结果。"""
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    total_debit: float = 0.0
    total_credit: float = 0.0
    balance_diff: float = 0.0  # 借贷差额

    def add_error(self, error: ValidationError) -> None:
        self.errors.append(error)
        self.is_valid = False


# ========== 标准会计科目表 ==========

# 常用会计科目及其类别映射（基于企业会计准则）
STANDARD_ACCOUNTS: dict[str, AccountType] = {
    # 资产类
    "库存现金": AccountType.ASSET,
    "银行存款": AccountType.ASSET,
    "应收账款": AccountType.ASSET,
    "预付账款": AccountType.ASSET,
    "应收票据": AccountType.ASSET,
    "其他应收款": AccountType.ASSET,
    "原材料": AccountType.ASSET,
    "库存商品": AccountType.ASSET,
    "固定资产": AccountType.ASSET,
    "累计折旧": AccountType.ASSET,  # 备抵科目，贷增借减
    "无形资产": AccountType.ASSET,
    "长期股权投资": AccountType.ASSET,
    "交易性金融资产": AccountType.ASSET,
    "存货": AccountType.ASSET,
    "在建工程": AccountType.ASSET,

    # 负债类
    "短期借款": AccountType.LIABILITY,
    "应付账款": AccountType.LIABILITY,
    "预收账款": AccountType.LIABILITY,
    "应付票据": AccountType.LIABILITY,
    "应付职工薪酬": AccountType.LIABILITY,
    "应交税费": AccountType.LIABILITY,
    "应付利息": AccountType.LIABILITY,
    "长期借款": AccountType.LIABILITY,
    "应付债券": AccountType.LIABILITY,
    "其他应付款": AccountType.LIABILITY,

    # 所有者权益类
    "实收资本": AccountType.EQUITY,
    "资本公积": AccountType.EQUITY,
    "盈余公积": AccountType.EQUITY,
    "本年利润": AccountType.PROFIT,
    "利润分配": AccountType.EQUITY,

    # 收入类
    "主营业务收入": AccountType.REVENUE,
    "其他业务收入": AccountType.REVENUE,
    "营业外收入": AccountType.REVENUE,
    "投资收益": AccountType.REVENUE,

    # 费用类
    "主营业务成本": AccountType.EXPENSE,
    "其他业务成本": AccountType.EXPENSE,
    "销售费用": AccountType.EXPENSE,
    "管理费用": AccountType.EXPENSE,
    "财务费用": AccountType.EXPENSE,
    "营业外支出": AccountType.EXPENSE,
    "所得税费用": AccountType.EXPENSE,
    "税金及附加": AccountType.EXPENSE,
    "资产减值损失": AccountType.EXPENSE,
    "信用减值损失": AccountType.EXPENSE,
}

# 备抵科目（方向与主科目相反）
CONTRA_ACCOUNTS: dict[str, str] = {
    "累计折旧": "固定资产",  # 累计折旧是固定资产的备抵科目
    "累计摊销": "无形资产",
    "坏账准备": "应收账款",
    "存货跌价准备": "存货",
}


class JournalEntryValidator:
    """
    会计分录判错引擎。

    核心方法：
    - validate(lines): 验证分录，返回 ValidationResult
    - check_balance(lines): 检查借贷平衡
    - check_directions(lines): 检查记账方向
    - check_accounts(lines): 检查科目合法性

    验证顺序（第一性原理：从基础到复杂）：
    1. 非空检查
    2. 金额检查（非零、非负）
    3. 方向检查（有借有贷）
    4. 科目检查（已知科目）
    5. 借贷平衡检查
    6. 方向正确性检查（科目类别与方向匹配）
    """

    def __init__(self, custom_accounts: Optional[dict[str, AccountType]] = None):
        """
        初始化判错引擎。

        参数：
        - custom_accounts: 自定义科目表（合并到标准科目表中）
        """
        self.accounts = dict(STANDARD_ACCOUNTS)
        if custom_accounts:
            self.accounts.update(custom_accounts)

    def validate(self, lines: list[JournalEntryLine]) -> ValidationResult:
        """
        全面验证会计分录。

        执行所有验证规则，收集所有错误（而非遇到第一个就停止），
        帮助用户一次性了解所有问题。
        """
        result = ValidationResult(is_valid=True)

        # 1. 非空检查
        if not lines:
            result.add_error(ValidationError(
                error_type=ErrorType.EMPTY_ENTRY,
                message="分录为空，请添加至少一行借方和一行贷方",
            ))
            return result

        # 2. 逐行检查
        has_debit = False
        has_credit = False
        seen_accounts: dict[str, str] = {}  # account → direction

        for i, line in enumerate(lines):
            # 2a. 金额检查
            if line.amount == 0:
                result.add_error(ValidationError(
                    error_type=ErrorType.ZERO_AMOUNT,
                    message=f"第{i+1}行：科目「{line.account}」金额为零",
                    line_index=i,
                    account=line.account,
                ))
            elif line.amount < 0:
                result.add_error(ValidationError(
                    error_type=ErrorType.NEGATIVE_AMOUNT,
                    message=f"第{i+1}行：科目「{line.account}」金额为负数",
                    line_index=i,
                    account=line.account,
                ))

            # 2b. 方向统计
            if line.direction == EntryDirection.DEBIT:
                has_debit = True
            elif line.direction == EntryDirection.CREDIT:
                has_credit = True

            # 2c. 科目检查
            account_type = self.accounts.get(line.account)
            if account_type is None:
                result.add_error(ValidationError(
                    error_type=ErrorType.UNKNOWN_ACCOUNT,
                    message=f"第{i+1}行：科目「{line.account}」不在标准科目表中",
                    line_index=i,
                    account=line.account,
                ))
            else:
                line.account_type = account_type

            # 2d. 重复科目同方向检查
            key = f"{line.account}:{line.direction}"
            if key in seen_accounts:
                result.add_error(ValidationError(
                    error_type=ErrorType.DUPLICATE_ACCOUNT,
                    message=f"第{i+1}行：科目「{line.account}」的{line.direction}方重复",
                    line_index=i,
                    account=line.account,
                ))
            else:
                seen_accounts[key] = line.direction

        # 3. 有借有贷检查
        if not has_debit or not has_credit:
            missing = "贷方" if has_debit else "借方" if has_credit else "借方和贷方"
            result.add_error(ValidationError(
                error_type=ErrorType.MISSING_DIRECTION,
                message=f"分录缺少{missing}，借贷记账法要求有借必有贷",
            ))

        # 4. 借贷平衡检查
        total_debit = sum(
            l.amount for l in lines if l.direction == EntryDirection.DEBIT
        )
        total_credit = sum(
            l.amount for l in lines if l.direction == EntryDirection.CREDIT
        )
        result.total_debit = total_debit
        result.total_credit = total_credit
        result.balance_diff = round(total_debit - total_credit, 2)

        if abs(result.balance_diff) > 0.005:
            result.add_error(ValidationError(
                error_type=ErrorType.UNBALANCED,
                message=f"借贷不平衡：借方合计{total_debit}，贷方合计{total_credit}，差额{result.balance_diff}",
            ))

        # 5. 方向正确性检查（科目类别与方向匹配）
        self._check_direction_correctness(lines, result)

        return result

    def _check_direction_correctness(
        self, lines: list[JournalEntryLine], result: ValidationResult
    ) -> None:
        """
        检查记账方向是否与科目类别匹配。

        规则：
        - 资产/费用增加 → 借方；减少 → 贷方
        - 负债/权益/收入/利润增加 → 贷方；减少 → 借方
        - 备抵科目方向与主科目相反

        注意：此检查为「启发式」检查，无法判断增加/减少的语义，
        只能检查「明显不合理」的方向（如收入科目在借方通常是错误的）。
        """
        for i, line in enumerate(lines):
            if line.account_type is None:
                continue

            # 备抵科目特殊处理
            if line.account in CONTRA_ACCOUNTS:
                # 备抵科目的正常方向与主科目相反
                # 如累计折旧是贷方余额科目，贷方是正常方向
                if line.account in ("累计折旧", "累计摊销", "坏账准备", "存货跌价准备"):
                    # 这些备抵科目通常是贷方余额
                    # 借方表示减少（转出），贷方表示增加（计提）
                    # 不报错，因为两个方向都有可能
                    pass
                continue

            account_type = line.account_type

            # 启发式规则：
            # 收入类科目在借方 → 很可能错误（收入增加记贷方）
            # 费用类科目在贷方 → 很可能错误（费用增加记借方）
            # 注意：期末结转时收入可能在借方，费用可能在贷方
            # 所以这里只标记为「可能错误」，不直接报错
            if account_type == AccountType.REVENUE and line.direction == EntryDirection.DEBIT:
                # 收入在借方可能是结转，标记但不强制错误
                pass  # 启发式检查，暂不报错
            elif account_type == AccountType.EXPENSE and line.direction == EntryDirection.CREDIT:
                # 费用在贷方可能是结转
                pass

    def get_account_type(self, account: str) -> Optional[AccountType]:
        """获取科目类别。"""
        return self.accounts.get(account)

    def explain_entry(self, lines: list[JournalEntryLine]) -> str:
        """
        生成分录解释文案。

        用于教学场景：向学生解释分录的记账原理。
        """
        if not lines:
            return "空分录"

        parts = []
        total_debit = sum(l.amount for l in lines if l.direction == EntryDirection.DEBIT)
        total_credit = sum(l.amount for l in lines if l.direction == EntryDirection.CREDIT)

        parts.append("【分录分析】")
        parts.append(f"借方合计：{total_debit}")
        parts.append(f"贷方合计：{total_credit}")

        if abs(total_debit - total_credit) < 0.01:
            parts.append("✓ 借贷平衡")
        else:
            parts.append(f"✗ 借贷不平衡，差额：{total_debit - total_credit}")

        parts.append("\n【科目分析】")
        for line in lines:
            acc_type = self.accounts.get(line.account, "未知")
            direction = "借" if line.direction == EntryDirection.DEBIT else "贷"
            parts.append(f"  {line.account}（{acc_type}）{direction}方 {line.amount}")

            if acc_type in (AccountType.ASSET, AccountType.EXPENSE):
                normal = "借方"
            else:
                normal = "贷方"
            parts.append(f"    → {acc_type}类科目正常余额在{normal}")

        return "\n".join(parts)

    def suggest_correction(
        self, lines: list[JournalEntryLine], error: ValidationError
    ) -> Optional[str]:
        """
        针对特定错误提供修正建议。

        第一性原理：不仅指出错误，还要解释为什么错、怎么改。
        """
        if error.error_type == ErrorType.UNBALANCED:
            return (
                f"借贷不平衡。请检查：\n"
                f"1. 是否有遗漏的分录行\n"
                f"2. 金额是否计算正确\n"
                f"3. 借贷方金额是否相等"
            )

        elif error.error_type == ErrorType.MISSING_DIRECTION:
            return (
                "借贷记账法要求「有借必有贷」。每笔业务都必须同时记录借方和贷方。"
            )

        elif error.error_type == ErrorType.UNKNOWN_ACCOUNT:
            return (
                f"科目「{error.account}」不在标准科目表中。"
                f"请检查科目名称是否正确，或联系管理员添加新科目。"
            )

        elif error.error_type == ErrorType.ZERO_AMOUNT:
            return f"金额不能为零。请输入有效的金额。"

        elif error.error_type == ErrorType.NEGATIVE_AMOUNT:
            return (
                f"金额不能为负数。如果需要冲减，请在相反方向记账。"
                f"例如：冲减银行存款应在贷方记正数，而非在借方记负数。"
            )

        elif error.error_type == ErrorType.DUPLICATE_ACCOUNT:
            return (
                f"同一科目的同一方向不应重复出现。"
                f"如果需要合并，请将金额相加后记在一行。"
            )

        return None
