"""题库数据完整性修复与解析增强（流水线编排层）。

本模块是修复流程的薄编排层：具体的文本工具函数位于 ``text_utils``，
解析四模块内容构建器位于 ``module_builders``，通用流水线框架位于
``pipeline``。本模块仅保留与数据库写操作强相关的修复步骤函数，并通过
:class:`FixPipeline` 将它们按原始顺序编排执行。

对外公开接口：
- ``fix_existing_database(db) -> dict``：在服务器启动时调用，修复已有数据库
  中的选项顺序与数据完整性问题，返回修复统计信息。
"""
import random

from sqlalchemy.orm import Session

from app.models import KnowledgePoint, Question
from app.question_data.helpers import (
    _add_question,
    _extract_number,
    _gen_judgment,
    _gen_single_choice,
    _is_pure_numeric,
)
from app.question_data.module_builders import enhance_explanations
from app.question_data.pipeline import FixPipeline, FixStep
from app.question_data.text_utils import (
    explanation_references_options,
    strip_dedup_suffixes,
)


def _shuffle_all_options(db: Session) -> int:
    """
    打乱所有题目的选项顺序，确保正确答案不总是第一个。

    核心思路：保持 label 固定为 A/B/C/D（按 rowid 顺序），
    只交换 content 和 is_correct 字段，避免标签与行顺序错乱。

    所有题型（含真题）全部参与打乱，避免"答案总在第一个"的问题。
    判断题特殊处理：随机交换 A/B 位置，确保约 50% 正确答案在 A、50% 在 B。
    """
    questions = db.query(Question).all()
    count = 0

    for q in questions:
        opts = list(q.options)
        if len(opts) <= 1:
            continue

        # 判断题：随机交换 A/B，同步更新 answer 字段
        if q.question_type == "judgment":
            # 先修复可能的异常：确保只有一个正确选项
            correct_opts = [o for o in opts if o.is_correct]
            if len(correct_opts) != 1:
                # 修复：根据 answer 文本重设 is_correct
                for o in opts:
                    o.is_correct = (o.content == q.answer)
            # 确保选项内容为"正确"和"错误"
            contents = [o.content for o in opts]
            if '正确' not in contents or '错误' not in contents:
                # 修复：重设选项内容
                opts[0].content = "正确"
                opts[0].is_correct = (q.answer == "正确")
                opts[1].content = "错误"
                opts[1].is_correct = (q.answer == "错误")
            else:
                if random.random() < 0.5:
                    opts[0].content, opts[1].content = opts[1].content, opts[0].content
                    opts[0].is_correct, opts[1].is_correct = opts[1].is_correct, opts[0].is_correct
            # answer 保持为"正确"或"错误"文本，前端通过 content 匹配
            count += 1
            continue

        # 解析中引用了选项字母（如"A选项"、"B属于"）的题目，跳过打乱，
        # 否则打乱后解析中的字母指向会与选项内容错位。
        if explanation_references_options(q.explanation):
            count += 1
            continue

        # 单选/多选题（含真题）：打乱内容和正确性标记
        contents = [o.content for o in opts]
        correct_flags = [o.is_correct for o in opts]
        paired = list(zip(contents, correct_flags))
        random.shuffle(paired)

        # 将打乱后的内容写回，label 保持 A/B/C/D 不变
        new_answer = None
        for i, opt in enumerate(opts):
            opt.content, opt.is_correct = paired[i]
            if opt.is_correct:
                new_answer = opt.label

        # 更新 answer 字段
        if new_answer:
            q.answer = new_answer

        count += 1

    return count


def _fix_options_and_data_integrity(db: Session) -> dict:
    """修复步骤 a-f：选项打乱、判断题修复、答案一致性、选项去重、后缀清理、标签规范化。

    本步骤对应原 ``fix_existing_database`` 主循环部分（单次遍历完成多类
    修复），并包含独立的 label 规范化二次遍历。返回该部分贡献的统计
    子字典，结束处提交事务。

    Returns:
        统计子字典，键包括 ``shuffled``/``judgment_fixed``/``answer_fixed``/
        ``total``/``suffix_cleaned``，以及发生过去重时的 ``dedup_fixed``。
    """
    stats = {"shuffled": 0, "judgment_fixed": 0, "answer_fixed": 0, "total": 0, "suffix_cleaned": 0}

    questions = db.query(Question).all()
    for q in questions:
        opts = list(q.options)
        if len(opts) <= 1:
            continue
        stats["total"] += 1

        # ★ 幂等保障：清除上次运行可能追加的去重后缀，防止 "（错误）（错误）" 叠加
        for opt in opts:
            cleaned = strip_dedup_suffixes(opt.content)
            if cleaned != opt.content:
                opt.content = cleaned
                stats["suffix_cleaned"] += 1

        if q.question_type == "judgment":
            # 修复判断题异常
            correct_opts = [o for o in opts if o.is_correct]
            contents = [o.content for o in opts]

            need_fix = False
            if len(correct_opts) != 1:
                need_fix = True
            if '正确' not in contents or '错误' not in contents:
                need_fix = True
            if len(contents) != len(set(contents)):
                need_fix = True

            if need_fix:
                stats["judgment_fixed"] += 1
                # 根据答案文本重建选项
                opts[0].content = "正确"
                opts[0].is_correct = (q.answer == "正确")
                if len(opts) > 1:
                    opts[1].content = "错误"
                    opts[1].is_correct = (q.answer == "错误")

            # 随机交换 A/B 位置
            if random.random() < 0.5:
                opts[0].content, opts[1].content = opts[1].content, opts[0].content
                opts[0].is_correct, opts[1].is_correct = opts[1].is_correct, opts[0].is_correct

        else:
            # 单选题：检查 answer 与 is_correct 是否一致
            correct_label = next((o.label for o in opts if o.is_correct), None)
            if correct_label and q.answer != correct_label:
                stats["answer_fixed"] += 1
                q.answer = correct_label
            # 恢复：如果没有 is_correct=True 的选项，根据 answer 字段重建
            if correct_label is None:
                stats["answer_fixed"] += 1
                for o in opts:
                    o.is_correct = (o.label == q.answer)
                correct_label = q.answer

            # 去重：检查是否有重复选项内容
            contents = [o.content for o in opts]
            if len(contents) != len(set(contents)):
                stats["dedup_fixed"] = stats.get("dedup_fixed", 0) + 1
                # 找到正确答案的内容
                correct_opt = next((o for o in opts if o.is_correct), None)
                correct_content = correct_opt.content if correct_opt else contents[0]
                # 去重：对重复的错误选项生成新内容
                seen_contents = {correct_content}
                for opt in opts:
                    if not opt.is_correct:
                        if opt.content in seen_contents:
                            # 仅当选项内容为纯数值时才用数值偏移修复
                            if _is_pure_numeric(opt.content):
                                base = _extract_number(opt.content)
                                if base is not None:
                                    for _try in range(50):
                                        offset = random.choice([1, -1, 2, -2, 10, -10, 100, -100, 0.5, -0.5])
                                        new_val = str(round(base + offset, 2) if isinstance(base, float) else int(base + offset))
                                        if new_val not in seen_contents:
                                            opt.content = new_val
                                            seen_contents.add(new_val)
                                            break
                            else:
                                # 文本型：追加序号后缀区分（每次运行前会被 strip_dedup_suffixes 清除，保证幂等）
                                for suffix in ['（错误）', '（不正确）', '（非）']:
                                    if opt.content + suffix not in seen_contents:
                                        opt.content = opt.content + suffix
                                        seen_contents.add(opt.content)
                                        break
                        else:
                            seen_contents.add(opt.content)

            # 解析中引用了选项字母的题目，跳过打乱以避免解析与选项错位
            if explanation_references_options(q.explanation):
                continue

            # 打乱选项顺序
            contents = [o.content for o in opts]
            correct_flags = [o.is_correct for o in opts]
            paired = list(zip(contents, correct_flags))
            random.shuffle(paired)

            new_answer = None
            for i, opt in enumerate(opts):
                opt.content, opt.is_correct = paired[i]
                if opt.is_correct:
                    new_answer = opt.label
            if new_answer:
                q.answer = new_answer

            # 最终去重检查：确保打乱后无重复选项
            final_contents = [o.content for o in opts]
            if len(final_contents) != len(set(final_contents)):
                stats["dedup_fixed"] = stats.get("dedup_fixed", 0) + 1
                seen = set()
                for opt in opts:
                    if opt.content in seen:
                        if _is_pure_numeric(opt.content):
                            base = _extract_number(opt.content)
                            if base is not None:
                                for _try in range(50):
                                    offset = random.choice([1, -1, 2, -2, 10, -10, 100, -100, 0.5, -0.5])
                                    new_val = str(round(base + offset, 2) if isinstance(base, float) else int(base + offset))
                                    if new_val not in seen:
                                        opt.content = new_val
                                        seen.add(new_val)
                                        break
                        else:
                            # 文本型：追加后缀区分（下次运行前会被 strip_dedup_suffixes 清除）
                            for suffix in ['（错误）', '（不正确）', '（非）']:
                                if opt.content + suffix not in seen:
                                    opt.content = opt.content + suffix
                                    seen.add(opt.content)
                                    break
                    else:
                        seen.add(opt.content)

            stats["shuffled"] += 1

    # 选项 label 规范化：确保按 id 排序后 label 为 A/B/C/D
    label_fixed = 0
    for q in db.query(Question).all():
        opts = sorted(q.options, key=lambda o: o.id)
        if len(opts) <= 1:
            continue
        expected = ["A", "B", "C", "D", "E", "F"][:len(opts)]
        actual = [o.label for o in opts]
        if actual != expected:
            # 找到当前正确答案的内容
            correct_content = None
            for o in opts:
                if o.is_correct:
                    correct_content = o.content
                    break
            # 重新分配 label
            for i, opt in enumerate(opts):
                opt.label = expected[i]
            # 更新 answer 字段
            if correct_content is not None:
                for opt in opts:
                    if opt.content == correct_content:
                        q.answer = opt.label
                        break
            label_fixed += 1
    if label_fixed:
        db.flush()

    db.commit()
    return stats


def _load_static_modules(db: Session) -> int:
    """从静态JSON文件加载四模块内容（explanation/simple_explanation/mnemonic/study_tip）。

    静态文件在构建时由 generate_static_modules.py 预先生成，
    包含每道题的四个答案模块，基于CPA知识库和题目具体内容生成。
    按题目内容哈希匹配，确保数据库重建后仍能正确关联。
    """
    import json
    from pathlib import Path

    static_path = Path(__file__).parent / "static_modules.json"
    if not static_path.exists():
        # 静态文件不存在时回退到动态生成
        return enhance_explanations(db)

    with open(static_path, "r", encoding="utf-8") as f:
        modules_data = json.load(f)

    # 建立内容前缀 → 四模块的映射（用于ID不匹配时的fallback）
    content_map = {}
    prefix_map = {}
    for item in modules_data:
        content_map[item["id"]] = item
        prefix = item.get("content_prefix", "")
        if prefix:
            prefix_map[prefix] = item

    count = 0
    matched = 0
    questions = db.query(Question).all()
    for q in questions:
        # 优先按ID匹配（同一数据库实例）
        item = content_map.get(q.id)
        if item:
            matched += 1
        else:
            # ID不匹配时按内容前缀匹配
            prefix = (q.content or "")[:50]
            item = prefix_map.get(prefix)

        if item:
            if item.get("explanation"):
                q.explanation = item["explanation"]
            if item.get("simple_explanation"):
                q.simple_explanation = item["simple_explanation"]
            if item.get("mnemonic"):
                q.mnemonic = item["mnemonic"]
            if item.get("study_tip"):
                q.study_tip = item["study_tip"]
            count += 1
        else:
            # 未匹配到的题目用动态生成兜底
            kp = q.knowledge_point
            kp_name = kp.name if kp else "本题考点"
            if not q.simple_explanation:
                q.simple_explanation = f"本题考查「{kp_name}」，理解原理即可作答。"
            if not q.mnemonic:
                q.mnemonic = f"记忆：{kp_name}的核心要点。"
            if not q.study_tip:
                q.study_tip = f"建议：{kp_name}是重要考点，务必掌握。"
            count += 1

    # 填充空知识点和考试信息
    _fill_empty_knowledge_points(db)
    _tag_exam_info(db)

    import logging
    logging.getLogger(__name__).info(
        f"静态模块加载: {matched}/{count} 题按ID匹配, {count - matched} 题按内容匹配"
    )

    return count


def _enhance_short_explanations(db: Session) -> int:
    """增强过短解析（<15字），补充题目上下文使其更易理解。"""
    count = 0
    for q in db.query(Question).all():
        if not q.explanation:
            continue
        exp = q.explanation.strip()
        if len(exp) >= 15:
            continue

        # 获取知识点名称作为上下文
        kp_name = ""
        if q.knowledge_point:
            kp_name = q.knowledge_point.name or ""

        # 根据题型构建增强后的解析
        if q.question_type == "judgment":
            if q.answer == "错误":
                prefix = f"该说法不正确。{exp}"
            else:
                prefix = f"该说法正确。{exp}"
            if kp_name:
                q.explanation = f"{prefix}（考点：{kp_name}）"
            else:
                q.explanation = prefix
        else:
            # 单选题：补充知识点上下文
            if kp_name:
                q.explanation = f"{exp}（考点：{kp_name}）"
            else:
                # 从题干提取关键词
                content = q.content or ""
                key_phrase = content[:20] if len(content) > 20 else content
                q.explanation = f"{exp}（{key_phrase}...）"

        count += 1

    return count


def _balance_judgment_answers(db: Session) -> int:
    """
    平衡判断题答案分布。

    如果"正确"答案占比超过60%，将部分"正确"题否定为"错误"题。
    否定方式：将原陈述否定（如"是"→"不是"），并翻转答案和解析。
    """
    judgment_qs = db.query(Question).filter(Question.question_type == "judgment").all()
    if not judgment_qs:
        return 0

    correct_qs = [q for q in judgment_qs if q.answer == "正确"]
    total = len(judgment_qs)
    correct_ratio = len(correct_qs) / total

    if correct_ratio <= 0.60:
        return 0  # 分布已足够平衡

    # 需要将部分"正确"题翻转为"错误"题
    target_correct = total // 2
    num_to_flip = len(correct_qs) - target_correct

    # 按ID排序，均匀选择要翻转的题目
    correct_qs.sort(key=lambda q: q.id)
    # 每隔一定间隔选一个，确保均匀分布
    step = len(correct_qs) / num_to_flip
    to_flip = [correct_qs[int(i * step)] for i in range(num_to_flip)]

    # 否定模式：按优先级匹配
    # 注意：短关键词（如"由"）容易在复合词中误匹配（如"理由"→"理不由"），已移除
    negate_patterns = [
        ("适用于", "不适用于"),  # 必须在"用于"之前
        ("是", "不是"),      # 但需避免"是否"中的"是"
        ("包括", "不包括"),
        ("属于", "不属于"),
        ("可以", "不可以"),
        ("应当", "不应当"),
        ("具有", "不具有"),
        ("能够", "不能够"),
        ("用于", "不用于"),
    ]

    count = 0
    for q in to_flip:
        content = q.content or ""
        explanation = q.explanation or ""

        # 跳过含转折连词的复合句，避免否定后产生自相矛盾（如"可以撤回，但不能撤销"→"不可以撤回，但不能撤销"）
        if any(conj in content for conj in ["但", "然而", "不过", "但是"]):
            continue

        # 尝试否定陈述
        negated = False
        for pattern, replacement in negate_patterns:
            # 找到第一个不在"否/只"后面的pattern
            idx = 0
            while idx < len(content):
                pos = content.find(pattern, idx)
                if pos == -1:
                    break
                # 检查前一个字是否为"否"或"只"
                if pos > 0 and content[pos - 1] in ("否", "只"):
                    idx = pos + 1
                    continue
                # 检查是否已经是"不X"形式
                if pos >= 1 and content[pos - 1] == "不":
                    idx = pos + 1
                    continue
                # 执行替换
                q.content = content[:pos] + replacement + content[pos + len(pattern):]
                negated = True
                break

        if not negated:
            # 无法通过模式否定，跳过此题（不翻转），避免产生"下列说法不正确"双重否定混淆
            continue

        # 翻转答案
        q.answer = "错误"

        # 更新解析：明确说明原命题正确但被否定后为错误
        q.explanation = f"该说法错误。{explanation}"

        # 更新选项的 is_correct
        for o in q.options:
            o.is_correct = (o.content == "错误")

        count += 1

    return count


def _tag_exam_info(db: Session) -> int:
    """
    为题目标注来源和考点。

    改进：考点直接使用知识点名称，确保考点与题干内容匹配。
    来源统一标记为 mock（模拟题），不再随机标记为真题，
    因为所有题目均为模板生成，非真实历年考题。
    """
    questions = db.query(Question).all()
    count = 0

    # 知识点名称 → 考点说明的精确映射
    kp_to_exam_point = {
        # 会计
        "借贷记账法": "借贷记账法的基本规则与应用",
        "会计要素与会计等式": "会计要素确认与会计等式运用",
        "会计信息质量要求": "会计信息质量要求的理解与判断",
        "会计计量属性": "会计计量属性的选择与应用",
        "会计政策与会计估计": "会计政策与会计估计变更",
        "存货的初始计量": "存货的初始计量与入账价值确定",
        "存货的期末计量": "存货期末计量与跌价准备",
        "固定资产的初始计量": "固定资产初始计量与入账价值",
        "固定资产折旧": "固定资产折旧方法与计算",
        "固定资产的处置": "固定资产处置损益的确认",
        "无形资产": "无形资产的确认、摊销与处置",
        "投资性房地产": "投资性房地产的确认与计量",
        "长期股权投资": "长期股权投资的成本法与权益法",
        "资产减值": "资产减值测试与减值准备",
        "流动负债": "流动负债的确认与计量",
        "职工薪酬": "职工薪酬的确认与计量",
        "借款费用": "借款费用资本化的条件与计算",
        "股份支付": "股份支付的会计处理",
        "或有事项": "或有事项的确认与披露",
        "金融工具": "金融资产的分类与计量",
        "所有者权益": "所有者权益的构成与变动",
        "收入的确认与计量": "收入确认五步法应用",
        "费用的确认": "费用的确认与计量",
        "政府补助": "政府补助的确认与计量",
        "非货币性资产交换": "非货币性资产交换的认定与计量",
        "债务重组": "债务重组损益的确认与计量",
        "所得税": "所得税的递延税处理",
        "外币折算": "外币交易的折算与汇兑损益",
        "租赁": "租赁使用权资产与租赁负债",
        "财务报告": "财务报表的编制与列报",
        "现金流量表": "现金流量表的编制方法",
        "资产负债表日后事项": "资产负债表日后事项的会计处理",
        "企业合并": "企业合并的会计处理（同一控制/非同一控制）",
        "合并财务报表": "合并报表的合并范围与抵销分录",
        # 审计
        "审计概念与目标": "审计目标的认定与理解",
        "审计要素与保证程度": "审计要素与合理保证/有限保证",
        "审计计划": "总体审计策略与具体审计计划",
        "重要性": "重要性水平的确定与应用",
        "审计证据": "审计证据的充分性与适当性",
        "审计程序": "审计程序的设计与执行",
        "函证": "函证程序的设计与实施",
        "分析程序": "分析程序在审计中的运用",
        "审计抽样": "审计抽样的样本选取与评价",
        "审计工作底稿": "审计工作底稿的编制与归档",
        "风险评估": "风险评估程序与了解被审计单位",
        "审计风险模型": "审计风险模型的运用",
        "风险应对": "进一步审计程序的设计",
        "内部控制": "内部控制的了解与测试",
        "销售与收款循环审计": "销售与收款循环的审计测试",
        "采购与付款循环审计": "采购与付款循环的审计测试",
        "生产与存货循环审计": "生产与存货循环的审计测试",
        "货币资金审计": "货币资金的审计程序",
        "舞弊与法律法规": "舞弊风险的识别与应对",
        "完成审计工作": "审计完成阶段的工作",
        "审计报告": "审计报告的意见类型",
        "内部控制审计": "内部控制审计的要点",
        "职业道德与独立性": "审计职业道德与独立性要求",
        # 财务成本管理
        "财务管理基本原理": "财务管理目标与利益相关者",
        "资金时间价值": "资金时间价值与复利计算",
        "风险与报酬": "风险与报酬的衡量与权衡",
        "财务报表分析": "财务比率分析与杜邦分析",
        "财务预测": "财务预测与可持续增长率",
        "资本成本": "资本成本的计算与WACC",
        "WACC": "资本成本的计算与WACC",
        "加权平均资本成本": "资本成本的计算与WACC",
        "投资项目资本预算": "净现值NPV与投资决策",
        "债券价值评估": "债券估值模型与应用",
        "股票价值评估": "股票估值模型与应用",
        "期权价值评估": "期权定价模型与应用",
        "企业价值评估": "企业价值评估方法",
        "资本结构": "资本结构理论与杠杆系数",
        "长期筹资": "长期筹资方式与资本成本",
        "营运资本管理": "营运资本投资与筹资策略",
        "产品成本计算": "产品成本的计算方法",
        "标准成本法": "标准成本差异分析",
        "作业成本法": "作业成本分配与管理",
        "本量利分析": "本量利分析与盈亏平衡点",
        "短期经营决策": "短期经营决策分析",
        "全面预算": "全面预算的编制方法",
        # 公司战略与风险管理
        "战略与战略管理": "战略层次与战略管理过程",
        "宏观环境分析": "PEST宏观环境分析",
        "产业环境分析": "波特五力模型分析",
        "SWOT分析": "SWOT分析与应用",
        "价值链分析": "价值链分析与应用",
        "总体战略": "总体战略（发展战略/稳定战略）",
        "竞争战略": "成本领先与差异化战略",
        "国际化经营战略": "国际化战略的选择与动因",
        "战略实施": "战略实施与组织结构",
        "公司治理": "公司治理结构与机制",
        "风险与风险管理概述": "风险类型与风险管理基本框架",
        "风险管理方法": "风险应对策略与方法",
        "内部控制": "内部控制要素与应用",
        "风险管理框架": "企业风险管理框架（COSO-ERM）",
        # 经济法
        "法律基本原理": "法律渊源与法律关系",
        "基本民事法律制度": "民事法律行为与代理",
        "物权法律制度": "物权变动规则与物权保护",
        "合同法基本原理": "合同的成立与生效",
        "合同的履行与违约": "合同履行与违约责任",
        "典型合同": "典型合同（买卖/租赁/借款等）",
        "合伙企业法": "合伙企业的设立与责任承担",
        "公司法基本制度": "公司设立与股东权利义务",
        "公司治理结构": "公司治理结构（股东会/董事会/监事会）",
        "公司合并分立与清算": "公司合并、分立与清算程序",
        "证券法律制度": "证券发行与信息披露",
        "企业破产法": "破产申请与重整程序",
        "票据法": "票据背书转让与权利义务",
        "支付结算法律制度": "支付结算方式与规则",
        # 税法
        "税法总论": "税法基本原则与税法要素",
        "增值税基本原理": "增值税基本原理与纳税人",
        "增值税销项税额": "增值税销项税额计算",
        "增值税进项税额": "增值税进项税额抵扣",
        "增值税征收管理": "增值税征收管理规定",
        "消费税": "消费税的计征方法",
        "企业所得税": "企业所得税应纳税所得额计算",
        "企业所得税税收优惠": "企业所得税税收优惠政策",
        "个人所得税": "个人所得税综合所得计算",
        "个人所得税专项附加扣除": "个人所得税专项附加扣除",
        "城市维护建设税": "城建税的计算与缴纳",
        "关税法": "关税的完税价格与计算",
        "土地增值税": "土地增值税的计算",
        "印花税": "印花税征税范围与计算",
        "国际税收": "国际税收抵免与避税",
        "税收征收管理法": "税收征管法的基本规定",
    }

    for q in questions:
        # 跳过已标记为真题的题目，保留其原始标注
        if q.source == "past_exam":
            continue

        kp = q.knowledge_point
        kp_name = kp.name if kp else "综合知识点"

        # 直接使用知识点名称映射考点
        # 不再从题干内容中匹配关键词，因为通用词汇（如"所有者权益"、"所得税"、
        # "增值税进项税额"）会出现在大量不相关题目中，导致75%以上的误匹配
        q.exam_point = kp_to_exam_point.get(kp_name, kp_name)

        # 模拟题统一标记来源
        q.source = "mock"
        q.exam_year = None

        count += 1

    return count


def _fill_empty_knowledge_points(db: Session) -> int:
    """为没有题目的知识点生成基础概念题。"""
    from sqlalchemy import func as sqlfunc
    labels_4 = ["A", "B", "C", "D"]
    count = 0

    kps = db.query(KnowledgePoint).all()
    for kp in kps:
        q_count = db.query(sqlfunc.count(Question.id)).filter(
            Question.knowledge_point_id == kp.id
        ).scalar()
        if q_count > 0:
            continue

        # 为每个空知识点生成3道基础概念题
        # 题1: 概念辨析单选题
        content1 = f"关于「{kp.name}」，下列说法正确的是（　）。"
        result1 = _gen_single_choice(
            content1, "A",
            f"{kp.name}：{kp.description}。这是{kp.subject}科目{kp.chapter}的核心知识点。",
            min(kp.difficulty, 3),
            [("A", f"以上描述符合{kp.name}的定义和要求"),
             ("B", f"{kp.name}不需要进行会计处理"),
             ("C", f"{kp.name}仅适用于上市公司"),
             ("D", f"{kp.name}属于非重要事项，可忽略")]
        )
        _add_question(db, kp.id, result1[0], result1[1], result1[2], result1[3], result1[4], "mock", result1[5])
        count += 1

        # 题2: 章节归属判断题
        content2 = f"{kp.name}属于{kp.subject}科目的考试内容。（　）"
        result2 = _gen_judgment(content2, True, f"{kp.name}是{kp.subject}科目{kp.chapter}的重要考点。", 1)
        _add_question(db, kp.id, result2[0], result2[1], result2[2], result2[3], result2[4], "mock", result2[5])
        count += 1

        # 题3: 难度/理解判断题
        content3 = f"{kp.name}的基本原理可以简单地概括为：{kp.description}。（　）"
        result3 = _gen_judgment(content3, True, f"{kp.name}的核心要点即为其基本原理，需要理解掌握。", 2)
        _add_question(db, kp.id, result3[0], result3[1], result3[2], result3[3], result3[4], "mock", result3[5])
        count += 1

    return count


# ========== 流水线步骤包装函数 ==========
# 每个包装函数调用对应的修复逻辑函数（返回 int 计数），提交事务，
# 并将其封装为统计子字典（供 FixPipeline.run 合并）。


def _step_enhance_short_explanations(db: Session) -> dict:
    """修复步骤 g：增强过短解析。"""
    count = _enhance_short_explanations(db)
    db.commit()
    return {"short_explanation_enhanced": count}


def _step_balance_judgment_answers(db: Session) -> dict:
    """修复步骤 h：平衡判断题答案分布。"""
    count = _balance_judgment_answers(db)
    db.commit()
    return {"judgment_balanced": count}


def _step_load_static_modules(db: Session) -> dict:
    """修复步骤 i：加载静态解析四模块（内部含空知识点补充 j 与考点标注 k）。"""
    count = _load_static_modules(db)
    db.commit()
    return {"enhanced": count}


def _final_judgment_answer_fix(db: Session) -> dict:
    """修复步骤 l：最终判断题 answer 与正确选项 label 一致性修复。

    判断题 answer 修复（须在 _balance_judgment_answers 之后执行）：
    选项打乱后 answer 字段可能仍为"正确"/"错误"文本，而正确选项的 label
    已变为 A/B。由于 _balance_judgment_answers 依赖 answer 为"正确"/"错误"
    文本来平衡正误分布，本修复放在其后，统一将 answer 设置为正确选项的 label，
    使其与单选题保持一致（如 Q4 answer="正确" 但正确选项 label="B"）。
    """
    judgment_answer_fixed = 0
    for q in db.query(Question).all():
        if q.question_type != "judgment":
            continue
        correct_opt = next((o for o in q.options if o.is_correct), None)
        if correct_opt is None:
            continue
        if q.answer != correct_opt.label:
            q.answer = correct_opt.label
            judgment_answer_fixed += 1
    if judgment_answer_fixed:
        db.flush()
        db.commit()
    return {"judgment_answer_fixed": judgment_answer_fixed}


def fix_existing_database(db: Session) -> dict:
    """
    修复已有数据库中的选项顺序和数据完整性问题。

    在服务器启动时自动调用，无需删除数据库重建。
    修复内容：
    1. 打乱所有题目的选项顺序（包括真题单选题）
    2. 修复判断题的数据异常（两个正确选项、缺失选项等）
    3. 确保单选题的 answer 字段与 is_correct 选项的 label 一致
    4. 添加新列（simple_explanation/mnemonic/study_tip）到已有表
    5. 刷新解析四模块（详细解析/通俗解释/记忆口诀/小贴士）

    通过 :class:`FixPipeline` 按原始顺序编排执行各修复步骤，返回汇总的
    修复统计信息（与重构前格式完全一致）。
    """
    pipeline = FixPipeline()
    pipeline.add_step(FixStep(
        name="fix_options_and_labels",
        description="步骤 a-f：选项打乱/判断题修复/答案一致性/去重/后缀清理/标签规范化",
        fn=_fix_options_and_data_integrity,
    ))
    pipeline.add_step(FixStep(
        name="enhance_short_explanations",
        description="步骤 g：增强过短解析（<15字）补充上下文",
        fn=_step_enhance_short_explanations,
    ))
    pipeline.add_step(FixStep(
        name="balance_judgment_answers",
        description="步骤 h：平衡判断题答案分布",
        fn=_step_balance_judgment_answers,
    ))
    pipeline.add_step(FixStep(
        name="load_static_modules",
        description="步骤 i：加载静态解析四模块（含空知识点补充 k 与考点标注 j）",
        fn=_step_load_static_modules,
    ))
    pipeline.add_step(FixStep(
        name="final_judgment_answer_fix",
        description="步骤 l：最终判断题 answer 与正确选项 label 一致性修复",
        fn=_final_judgment_answer_fix,
    ))
    return pipeline.run(db)
