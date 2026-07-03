"""大规模题目生成编排入口。"""
import logging

from sqlalchemy.orm import Session

from app.question_data.fixes import _shuffle_all_options
from app.question_data.generators import (
    gen_accounting,
    gen_accounting_batch3,
    gen_accounting_batch4,
    gen_accounting_extra,
    gen_all_subjects_concepts,
    gen_all_subjects_judgments,
    gen_auditing,
    gen_auditing_batch4,
    gen_auditing_extra,
    gen_concepts_batch5,
    gen_finance,
    gen_finance_batch3,
    gen_judgments_batch5,
    gen_law,
    gen_law_batch4,
    gen_law_extra,
    gen_strategy,
    gen_strategy_batch4,
    gen_strategy_extra,
    gen_tax,
    gen_tax_batch3,
    gen_tax_extra,
)
from app.question_data.module_builders import enhance_explanations
from app.question_data.past_exams import _import_past_exams

logger = logging.getLogger("app.question_data.orchestrator")


def generate_mass_questions(db: Session) -> int:
    """
    批量生成 5000+ 道题目。
    返回总生成数量。
    """
    # 确保知识点存在
    from app.seed_data import seed_knowledge_points
    code_to_id = seed_knowledge_points(db)

    total = 0
    total += gen_accounting(db, code_to_id)
    db.commit()

    total += gen_auditing(db, code_to_id)
    db.commit()

    total += gen_finance(db, code_to_id)
    db.commit()

    total += gen_strategy(db, code_to_id)
    db.commit()

    total += gen_law(db, code_to_id)
    db.commit()

    total += gen_tax(db, code_to_id)
    db.commit()

    # 第二批扩展题目
    prev = total
    total += gen_accounting_extra(db, code_to_id)
    db.commit()
    logger.info("  会计(扩展): %d 题", total - prev)

    prev = total
    total += gen_auditing_extra(db, code_to_id)
    db.commit()
    logger.info("  审计(扩展): %d 题", total - prev)

    prev = total
    total += gen_strategy_extra(db, code_to_id)
    db.commit()
    logger.info("  战略(扩展): %d 题", total - prev)

    prev = total
    total += gen_law_extra(db, code_to_id)
    db.commit()
    logger.info("  经济法(扩展): %d 题", total - prev)

    prev = total
    total += gen_tax_extra(db, code_to_id)
    db.commit()
    logger.info("  税法(扩展): %d 题", total - prev)

    # 第三批大规模扩展题目
    prev = total
    total += gen_accounting_batch3(db, code_to_id)
    db.commit()
    logger.info("  会计(第三批): %d 题", total - prev)

    prev = total
    total += gen_finance_batch3(db, code_to_id)
    db.commit()
    logger.info("  财管(第三批): %d 题", total - prev)

    prev = total
    total += gen_all_subjects_judgments(db, code_to_id)
    db.commit()
    logger.info("  全科目判断题: %d 题", total - prev)

    prev = total
    total += gen_all_subjects_concepts(db, code_to_id)
    db.commit()
    logger.info("  全科目概念题: %d 题", total - prev)

    prev = total
    total += gen_tax_batch3(db, code_to_id)
    db.commit()
    logger.info("  税法(第三批): %d 题", total - prev)

    # 第四批补充薄弱科目
    prev = total
    total += gen_auditing_batch4(db, code_to_id)
    db.commit()
    logger.info("  审计(第四批): %d 题", total - prev)

    prev = total
    total += gen_strategy_batch4(db, code_to_id)
    db.commit()
    logger.info("  战略(第四批): %d 题", total - prev)

    prev = total
    total += gen_law_batch4(db, code_to_id)
    db.commit()
    logger.info("  经济法(第四批): %d 题", total - prev)

    prev = total
    total += gen_accounting_batch4(db, code_to_id)
    db.commit()
    logger.info("  会计(第四批): %d 题", total - prev)

    # 第五批概念与判断题
    prev = total
    total += gen_concepts_batch5(db, code_to_id)
    db.commit()
    logger.info("  概念题(第五批): %d 题", total - prev)

    prev = total
    total += gen_judgments_batch5(db, code_to_id)
    db.commit()
    logger.info("  判断题(第五批): %d 题", total - prev)

    # 导入历年真题
    from app.past_exam_data import ALL_PAST_EXAMS
    past_count = _import_past_exams(db, code_to_id, ALL_PAST_EXAMS)
    db.commit()
    total += past_count
    logger.info("  历年真题: %d 题", past_count)

    # 打乱所有题目的选项顺序，避免正确答案总在A
    shuffled = _shuffle_all_options(db)
    db.commit()
    logger.info("  选项打乱: %d 题", shuffled)

    # 为解析追加通俗化记忆口诀
    enhanced = enhance_explanations(db)
    db.commit()
    logger.info("  解析增强: %d 题", enhanced)

    logger.info("  ======================")
    logger.info("  总计: %d 题", total)
    return total
