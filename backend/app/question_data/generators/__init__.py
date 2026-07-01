"""各科目题目生成器集合，统一导出全部 gen_* 函数。"""
from app.question_data.generators.accounting import (
    gen_accounting,
    gen_accounting_batch3,
    gen_accounting_batch4,
    gen_accounting_extra,
)
from app.question_data.generators.auditing import (
    gen_auditing,
    gen_auditing_batch4,
    gen_auditing_extra,
)
from app.question_data.generators.common import (
    gen_all_subjects_concepts,
    gen_all_subjects_judgments,
    gen_concepts_batch5,
    gen_judgments_batch5,
)
from app.question_data.generators.finance import gen_finance, gen_finance_batch3
from app.question_data.generators.law import gen_law, gen_law_batch4, gen_law_extra
from app.question_data.generators.strategy import (
    gen_strategy,
    gen_strategy_batch4,
    gen_strategy_extra,
)
from app.question_data.generators.tax import gen_tax, gen_tax_batch3, gen_tax_extra

__all__ = [
    "gen_accounting",
    "gen_accounting_batch3",
    "gen_accounting_batch4",
    "gen_accounting_extra",
    "gen_all_subjects_concepts",
    "gen_all_subjects_judgments",
    "gen_auditing",
    "gen_auditing_batch4",
    "gen_auditing_extra",
    "gen_concepts_batch5",
    "gen_finance",
    "gen_finance_batch3",
    "gen_judgments_batch5",
    "gen_law",
    "gen_law_batch4",
    "gen_law_extra",
    "gen_strategy",
    "gen_strategy_batch4",
    "gen_strategy_extra",
    "gen_tax",
    "gen_tax_batch3",
    "gen_tax_extra",
]
