"""题库数据完整性修复与解析增强。"""
import random
import re

from sqlalchemy.orm import Session

from app.models import KnowledgePoint, Question
from app.question_data.helpers import (
    _add_question,
    _extract_number,
    _gen_judgment,
    _gen_single_choice,
    _is_pure_numeric,
)

# 匹配解析中引用选项字母的模式。
# 形如 "A选项"、"A属于"、"A、"、"A（内容）"、"A(内容)"、"A多元化" 等，
# 即单个大写字母 A-D 紧跟"选项"二字、中文标点或任意中文字符。
_OPTION_LETTER_RE = re.compile(r"[A-D](?:选项|[、，。（(]|[一-鿿])")

# 去重时可能追加的后缀（需在每次修复前清除，防止"（错误）（错误）"叠加）
_DEDUP_SUFFIXES = ["（错误）", "（不正确）", "（非）", "（ variant）", "（变体1）", "（变体2）", "（变体3）"]


def _strip_dedup_suffixes(content: str) -> str:
    """清除选项内容中累积的去重后缀。

    fix_existing_database 每次服务器启动时运行，如果上次运行追加了
    "（错误）" 等后缀来消重，下次运行可能再次追加导致 "（错误）（错误）"
    叠加。此函数在处理前先清除所有已知后缀，确保幂等。
    """
    changed = True
    while changed:
        changed = False
        for suffix in _DEDUP_SUFFIXES:
            if content.endswith(suffix):
                content = content[: -len(suffix)]
                changed = True
    return content


def _explanation_references_options(explanation: str) -> bool:
    """检测解析文本是否引用了选项字母（A/B/C/D）。

    若解析中包含选项字母引用，打乱选项顺序会导致解析中的字母指向
    与打乱后的选项内容错位，因此这类题目应跳过选项打乱。
    """
    if not explanation:
        return False
    return bool(_OPTION_LETTER_RE.search(explanation))


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
        if _explanation_references_options(q.explanation):
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

    返回修复统计信息。
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
            cleaned = _strip_dedup_suffixes(opt.content)
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
                                # 文本型：追加序号后缀区分（每次运行前会被 _strip_dedup_suffixes 清除，保证幂等）
                                for suffix in ['（错误）', '（不正确）', '（非）']:
                                    if opt.content + suffix not in seen_contents:
                                        opt.content = opt.content + suffix
                                        seen_contents.add(opt.content)
                                        break
                        else:
                            seen_contents.add(opt.content)

            # 解析中引用了选项字母的题目，跳过打乱以避免解析与选项错位
            if _explanation_references_options(q.explanation):
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
                            # 文本型：追加后缀区分（下次运行前会被 _strip_dedup_suffixes 清除）
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

    # 增强过短解析（<15字的explanation补充上下文）
    short_enhanced = _enhance_short_explanations(db)
    db.commit()
    stats["short_explanation_enhanced"] = short_enhanced

    # 平衡判断题答案分布（将部分"正确"题改为"错误"题）
    balanced = _balance_judgment_answers(db)
    db.commit()
    stats["judgment_balanced"] = balanced

    # 刷新解析提示（清除旧版通用提示，应用新的多样化提示）
    enhanced = _load_static_modules(db)
    db.commit()
    stats["enhanced"] = enhanced

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
        return _enhance_explanations(db)

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


# ========== 解析增强：通俗化 + 记忆口诀 ==========

# 关键词 → 记忆口诀映射表
_MNEMONIC_RULES: list[tuple[str, str]] = [
    # --- 最高优先级：长关键词/复合关键词（必须放在短关键词之前，避免误匹配） ---

    # 跨学科易混淆：合同法"标的物毁损灭失的风险转移"须先匹配，避免误匹配战略"风险转移"
    ("标的物毁损灭失", "💡 记忆口诀：标的物毁损灭失的风险，交付前由出卖人承担，交付后由买受人承担。"),
    # 跨学科易混淆：战略"风险应对策略"须先匹配，避免误匹配会计"固定资产"
    ("风险应对策略", "💡 记忆口诀：风险应对四策略——规避(不做)、降低(减少)、转移(保险/外包)、接受(自担)。"),
    # 跨学科易混淆：战略"购买保险"须先匹配，避免误匹配会计"固定资产"
    ("购买保险", "💡 记忆口诀：风险转移=把风险甩给别人，买保险、外包、套期保值。"),

    # WACC 必须在"加权平均"之前（WACC题目含"加权平均资本成本"会误匹配）
    ("WACC", "💡 记忆口诀：WACC = 借钱成本(税后) × 借钱比例 + 股东要求回报 × 股东比例。利息能抵税所以要「税后」，股利不能抵税。整体就是「融资的代价」。"),
    ("加权平均资本成本", "💡 记忆口诀：WACC = 借钱成本(税后) × 借钱比例 + 股东要求回报 × 股东比例。利息能抵税所以要「税后」，股利不能抵税。整体就是「融资的代价」。"),

    # 营业利润必须在"营业收入"之前（营业利润题目含"营业收入"会误匹配）
    ("营业利润", "💡 记忆口诀：营业利润 = 收入 - 成本 - 费用。简单说就是「赚的 - 花的 - 烧的」= 真正留在口袋的。"),

    # 固定资产减值/资产减值必须在"坏账准备"之前（减值题目含"减值准备"会误匹配"坏账准备"）
    ("固定资产减值", "💡 记忆口诀：长期资产减值一经计提不得转回（固定/无形/长投）。可收回金额=max(公允-处置费, 现值)。存货跌价和坏账准备可以转回。"),
    ("资产减值", "💡 记忆口诀：可收回金额=max(公允-处置费, 未来现金流量现值)。减值=账面-可收回。存货特殊：成本vs可变现净值取低。"),
    ("减值准备", "💡 记忆口诀：长期资产减值一经计提不得转回（固定/无形/长投）。存货跌价和坏账准备可以转回。区分「能转回」和「不能转回」是考点。"),

    # 审计意见/审计报告必须在"审计证据"之前
    ("审计报告", "💡 记忆口诀：审计意见四类——无保留(干净)、保留(有小问题)、否定(有大错)、无法表示(查不了)。措辞很讲究。"),
    ("否定意见", "💡 记忆口诀：审计意见四类——无保留(干净)、保留(有小问题)、否定(有大错)、无法表示(查不了)。措辞很讲究。"),
    ("无法表示意见", "💡 记忆口诀：审计意见四类——无保留(干净)、保留(有小问题)、否定(有大错)、无法表示(查不了)。措辞很讲究。"),

    # 价值链相关（题目可能不含"价值链"三字，但含"基本活动"/"主体活动"）
    ("基本活动", "💡 记忆口诀：价值链 = 主体活动(进料-生产-发货-销售-售后) + 辅助活动(采购/技术/人力/基建)。每环都在创造价值。"),
    ("主体活动", "💡 记忆口诀：价值链 = 主体活动(进料-生产-发货-销售-售后) + 辅助活动(采购/技术/人力/基建)。每环都在创造价值。"),
    ("辅助活动", "💡 记忆口诀：价值链 = 主体活动(进料-生产-发货-销售-售后) + 辅助活动(采购/技术/人力/基建)。每环都在创造价值。"),

    # 收入准则相关（必须在"承诺"之前，避免"可明确区分商品的承诺"误匹配经济法"承诺"）
    ("履约义务", "💡 记忆口诀：履约义务 = 可明确区分的商品/服务承诺。某一时段履约按进度确认收入，某一时点履约在控制权转移时确认。"),
    ("收入确认", "💡 记忆口诀：收入确认五步法：识别合同→识别履约义务→确定交易价格→分摊交易价格→确认收入。"),

    # 存货跌价（必须在"存货入账"之前）
    ("存货跌价", "💡 记忆口诀：存货跌价 = 成本 vs 可变现净值取低。成本>可变现净值才计提，计提后可以转回（区别于长期资产减值不得转回）。"),
    ("可变现净值", "💡 记忆口诀：可变现净值 = 估计售价 - 估计加工成本 - 估计销售费用。存货按成本与可变现净值孰低计量。"),

    # 审计抽样（题目可能用"属性抽样"/"抽样"而非"审计抽样"）
    ("属性抽样", "💡 记忆口诀：抽样风险 = 抽到的样本不代表总体。样本量越大风险越小，但成本也越高。权衡是关键。"),
    ("抽样", "💡 记忆口诀：抽样风险 = 抽到的样本不代表总体。样本量越大风险越小，但成本也越高。权衡是关键。"),

    # --- 高优先级专用口诀 ---
    ("土地增值税", "💡 记忆口诀：土地增值税四级超率累进——30/40/50/60%，速扣系数0/5%/15%/35%。增值率越高税率越高。"),
    ("消费税", "💡 记忆口诀：消费税=从价+从量。从价=不含税销售额×比例税率，从量=销售数量×定额税率。白酒、卷烟用复合计征。"),
    ("债务重组", "💡 记忆口诀：债权人按放弃债权公允价值计量受让资产，差额计入投资收益。债务人差额计入其他收益。"),
    ("政府补助", "💡 记忆口诀：总额法：补助先入递延收益，按资产寿命分期转其他收益。净额法：直接冲减资产成本或费用。"),
    ("财务报告", "💡 记忆口诀：四表一注——资产负债表、利润表、现金流量表、所有者权益变动表+附注。附注是「补充说明书」。"),

    # --- 会计 ---
    ("坏账准备", "💡 记忆口诀：坏账准备 = 余额 × 比例，就像「按比例存钱防坏账」。应收越多、比例越高，准备金越多。"),
    ("所有者权益", "💡 记忆口诀：所有者权益 = 本钱(实收资本) + 存粮(盈余公积) + 余粮(未分配利润)。三大块加一起就是股东的家底。"),
    ("盈余公积", "💡 记忆口诀：盈余公积是从利润里「抠」出来存着防饥荒的，像「强制储蓄」。"),
    ("双倍余额递减", "💡 记忆口诀：双倍余额 = 账面价值 × (2 ÷ 年限)。特点是「前期多折、后期少折」，像「吃苹果越吃越小」。最后两年改直线法收尾。"),
    ("年数总和", "💡 记忆口诀：年数总和法 = (原值-残值) × 尚可使用年数 ÷ 年数总和。分子越来越小，所以「折旧逐年递减」，像「下楼梯」。"),
    ("年限平均", "💡 记忆口诀：直线法最简单——每年折旧一样多，就像「均摊房租」，每月固定付一样。"),
    ("折旧", "💡 记忆口诀：折旧 = (原值 - 残值) ÷ 年限。把「能用多少年」分摊到每年，就像「切蛋糕」每人一份。残值是最后剩下的蛋糕底。"),
    ("存货入账", "💡 记忆口诀：存货成本 = 买价 + 运费 + 挑选费。记住「买进来 + 运回来 + 整理好」三步走，增值税不算在内（可以抵扣）。"),
    ("加权平均", "💡 记忆口诀：加权平均 = 总花钱 ÷ 总数量。就像「混在一起算均价」，不管哪批买的，统统平均。"),
    ("重要性水平", "💡 记忆口诀：重要性 = 基准 × 比例。就像「多少钱的错误你会介意」，金额越大越重要，小错误可以忽略。"),
    ("营业收入", "💡 记忆口诀：含税价 ÷ (1+税率) = 不含税收入。增值税是「价外税」，要「扒掉税皮」才是真正的收入。"),
    ("借贷记账", "💡 记忆口诀：「有借必有贷，借贷必相等」。资产费用增加记借方，负债收入增加记贷方。借 = 左边进，贷 = 右边出。"),
    ("无形资产", "💡 记忆口诀：无形资产 = 可辨认+无实物+非货币。自创商誉不算，研发支出符合条件才资本化。摊销看使用寿命，不定的不摊。"),
    ("长期股权投资", "💡 记忆口诀：成本法：只记减值不调损益。权益法：跟着被投资方净资产变动走。控制用成本法，重大影响/共同控制用权益法。"),
    ("固定资产", "💡 记忆口诀：固定资产 = 为生产持有 + 使用超过1年 + 单位价值较高。初始成本=买价+相关税费+安装调试费。"),
    ("应付账款", "💡 记忆口诀：应付账款 = 买了东西还没付钱。现金折扣用总价法，折扣期内付款享折扣计入财务收益。"),
    ("短期借款", "💡 记忆口诀：短期借款 = 1年内要还的借钱。利息按月计提计入财务费用，到期还本付息。"),
    ("实收资本", "💡 记忆口诀：实收资本 = 股东实际投入的本钱。增资走资本公积，减资要走法定程序公告债权人。"),

    # --- 审计 ---
    ("审计风险", "💡 记忆口诀：审计风险 = 重大错报风险 × 检查风险。就像「闯红灯被拍」= 你违规的概率 × 摄像头没拍到的概率。审计师只能控制「检查风险」。"),
    ("审计证据", "💡 记忆口诀：外部证据 > 内部证据，书面 > 口头。就像「银行流水」比「自己写的收据」可信，「签字盖章」比「口头说说」靠谱。"),
    ("内部控制", "💡 记忆口诀：内控五要素 = 环境是地基 + 风险评估是眼睛 + 控制活动是手脚 + 信息沟通是神经 + 监督是体检。缺一不可。"),
    ("函证", "💡 记忆口诀：函证 = 找第三方确认。银行确认存款借款，客户确认应收账款。第三方说的话最可信。"),
    ("控制测试", "💡 记忆口诀：控制测试 = 查「制度管不管用」。不是查具体数字对不对，而是查「流程有没有按规定执行」。"),
    ("实质性程序", "💡 记忆口诀：实质性程序 = 直接查数字对不对。函证、盘点、重新计算，都是「真刀真枪验真伪」。"),

    # --- 财务成本管理 ---
    ("资本成本", "💡 记忆口诀：资本成本 = 投资者要求的回报率。不是你花过的钱，而是「人家借你钱要的利息+股东要的分红」。"),
    ("流动比率", "💡 记忆口诀：流动比率 = 流动资产 ÷ 流动负债。就像「手头的钱 vs 短期欠的债」，大于2比较安全。"),
    ("速动比率", "💡 记忆口诀：速动比率 = (流动资产 - 存货) ÷ 流动负债。存货卖不掉不算，比流动比率更「严格」。一般大于1算健康。"),
    ("盈亏平衡", "💡 记忆口诀：盈亏平衡点 = 固定成本 ÷ (单价 - 变动成本)。就是「卖多少件才能不亏」。每件赚的(单价-变动)用来填固定成本的「坑」。"),
    ("边际贡献", "💡 记忆口诀：边际贡献 = 售价 - 变动成本。每多卖一件「额外赚的钱」，先填固定成本的坑，填完就是利润。"),
    ("安全边际", "💡 记忆口诀：安全边际 = 实际销量 - 盈亏平衡销量。就是「离亏本还有多远」，越大越安全。"),
    ("复利现值", "💡 记忆口诀：现值 = 终值 ÷ (1+利率)^年数。未来的一块钱不值现在的一块钱，要「打折」才公平。"),
    ("复利终值", "💡 记忆口诀：终值 = 现值 × (1+利率)^年数。钱生钱、利滚利，时间越长滚得越大，像「滚雪球」。"),
    ("年金", "💡 记忆口诀：年金 = 每期等额收付。就像「每月还房贷」金额一样，用专门的年金系数查表算。"),
    ("β系数", "💡 记忆口诀：β > 1 比大盘波动大(激进型)，β < 1 比大盘稳(保守型)，β = 1 跟大盘同步。是衡量「系统性风险」的尺子。"),
    ("名义利率", "💡 记忆口诀：名义利率 = 实际利率 + 通胀率。银行挂牌的是「名义」，真正购买力增长的是「实际」。费雪公式：1+名义 = (1+实际)(1+通胀)。"),
    ("净现值", "💡 记忆口诀：NPV = 未来现金流现值 - 初始投资。NPV>0就值得投，像「算总账看划不划算」。"),
    ("内部收益率", "💡 记忆口诀：IRR = 让NPV=0的折现率。IRR>资本成本就投，像「这笔投资本身的回报率够不够」。"),
    ("杜邦分析", "💡 记忆口诀：ROE = 净利率 × 周转率 × 权益乘数。赚钱能力×效率×杠杆三合一，拆开看就知道短板在哪。"),
    ("营运资金", "💡 记忆口诀：营运资金 = 流动资产 - 流动负债。正数说明短期不缺钱，负数要警惕资金链断裂。"),

    # --- 税法 ---
    ("销项税额", "💡 记忆口诀：销项税 = 不含税销售额 × 税率。卖东西收的税，是「你替税务局收的」，不是你的收入。"),
    ("进项税额", "💡 记忆口诀：进项税 = 买东西付的税，可以抵扣。买东西时「先垫的税」，卖东西时「收的税」来抵，差额上交。"),
    ("应纳增值税", "💡 记忆口诀：应交增值税 = 销项税 - 进项税。卖东西收的税减去买东西垫的税，差额就是「要上交国家的」。"),
    ("含税", "💡 记忆口诀：不含税价 = 含税价 ÷ (1+税率)。开发票要「扒掉税」看净额，就像「剥洋葱」去掉税那一层。"),
    ("企业所得税", "💡 记忆口诀：企业所得税 = 应纳税所得额 × 税率(一般25%)。高新企业15%，小型微利减按25%×20%=5%有效税率。"),
    ("个人所得税", "💡 记忆口诀：综合所得七级累进，3%→45%。「赚得越多税率越高」，先扣6万/年免征额，再扣专项附加。"),
    ("公益性捐赠", "💡 记忆口诀：公益捐赠限额 = 利润总额 × 12%。超过部分以后3年结转。做善事有上限，不是捐多少扣多少。"),
    ("增值税税率", "💡 记忆口诀：标准13%、9%(交通/农产品)、6%(服务)、0%(出口)。小规模3%征收率。区分税率vs征收率是关键。"),
    ("印花税", "💡 记忆口诀：印花税 = 合同金额 × 税率。签合同就要贴「邮票」，不同合同税率不同。实收资本也要交。"),
    ("房产税", "💡 记忆口诀：房产税 = 房产余值 × 1.2%(自用) 或 租金 × 12%(出租)。两种计税方式看用途。"),

    # --- 战略 ---
    ("SWOT", "💡 记忆口诀：SWOT = 内部优劣(S/W) + 外部机威(O/T)。SO用优势抓机会，WT避免劣势遇威胁。ST多元化避威胁，WO扭转补劣势。"),
    ("波特五力", "💡 记忆口诀：五力 = 现有竞争者(内斗) + 新进入者(外来威胁) + 替代品(替代威胁) + 供应商议价 + 买方议价。五力越强行业越难赚。"),
    ("成本领先", "💡 记忆口诀：成本领先 = 做到行业最低成本。靠规模效应+精细管理，价格战时你最能扛。"),
    ("差异化", "💡 记忆口诀：差异化 = 做出别人做不到的特色。品牌、技术、服务独特，客户愿意付溢价。"),
    ("BCG矩阵", "💡 记忆口诀：BCG四象限——明星(高增长高份额，砸钱养)、现金牛(低增长高份额，挤奶用)、问题(高增长低份额，赌不赌)、瘦狗(双低，考虑扔)。"),
    ("PEST", "💡 记忆口诀：PEST = 政治(P) + 经济(E) + 社会(S) + 技术(T)。宏观环境四把刀，扫描外部大势用。"),
    ("风险接受", "💡 记忆口诀：风险接受 = 觉得风险太小懒得管。不是「不知道」，而是「知道但选择不管」，省事省钱。"),
    ("风险规避", "💡 记忆口诀：风险规避 = 不干了，直接退出。惹不起躲得起，比如不做某项业务。"),
    ("风险降低", "💡 记忆口诀：风险降低 = 内控+分散，把风险压到可接受。系安全带不等于不出事，但减轻后果。"),
    ("风险转移", "💡 记忆口诀：风险转移 = 买保险、外包，把风险甩给别人。花小钱让保险公司扛大雷。"),
    ("价值链", "💡 记忆口诀：价值链 = 主体活动(进料-生产-发货-销售-售后) + 辅助活动(采购/技术/人力/基建)。每环都在创造价值。"),
    ("核心竞争力", "💡 记忆口诀：核心竞争力 = 别人学不会、买不到、模仿不了的能力。是企业的「护城河」。"),

    # --- 审计：合理保证（必须在经济法"一般保证"之前，避免审计题误匹配） ---
    ("合理保证", "💡 记忆口诀：审计提供合理保证（高水平但非绝对），审阅提供有限保证（中等水平）。合理保证≠绝对保证，风险不能降为零。"),
    ("有限保证", "💡 记忆口诀：审计提供合理保证（高水平但非绝对），审阅提供有限保证（中等水平）。合理保证≠绝对保证，风险不能降为零。"),

    # --- 经济法 ---
    ("要约", "💡 记忆口诀：要约 = 「我正式提出条件，你同意就成交」。内容必须具体确定，有约束力。要约邀请只是「广告」，没有约束力。"),
    ("承诺到达", "💡 记忆口诀：承诺 = 「我同意你的条件」。承诺到达对方时合同成立。不能改条件，改了就是新要约。"),
    ("新要约", "💡 记忆口诀：承诺 = 「我同意你的条件」。承诺到达对方时合同成立。不能改条件，改了就是新要约。"),
    ("违约金", "💡 记忆口诀：违约金 = 合同约定赔多少就赔多少。过高可请求法院调低(超损失30%)，过低可调高。补偿为主，惩罚为辅。"),
    ("票据", "💡 记忆口诀：票据三特征——无因性、要式性、文义性。汇票/本票/支票各不同。"),
    ("定金", "💡 记忆口诀：定金不超过合同额20%。收方违约双倍返还，付方违约不退。定金+违约金只能选一个，不能两个都要。"),
    ("有限责任公司", "💡 记忆口诀：有限公司股东≤50人，以出资额为限担责。不设股东会可(一人公司)，董事会3人以上，股东认缴出资期限不得超过5年。"),
    ("股份有限公司", "💡 记忆口诀：股份公司发起人1-200人（2023新公司法），全部资本分等额股份。董事会3人以上，可上市募集资本。"),
    ("一般保证", "💡 记忆口诀：保证分一般保证和连带保证。一般保证有先诉抗辩权（先找债务人），连带保证没这个权利，债权人可以直找保证人。"),
    ("连带保证", "💡 记忆口诀：保证分一般保证和连带保证。一般保证有先诉抗辩权（先找债务人），连带保证没这个权利，债权人可以直找保证人。"),
    ("抵押", "💡 记忆口诀：抵押 = 不转移占有。不动产抵押要登记才生效，动产抵押合同签了就生效但登记才能对抗第三人。"),
    ("质押", "💡 记忆口诀：质押 = 转移占有。动产质押交付时生效，权利质押要登记或交付权利凭证。和抵押的区别就是「东西要不要交出来」。"),

    # --- 通用会计原则 ---
    ("试算平衡", "💡 记忆口诀：试算平衡 = 借方合计 = 贷方合计。但平衡不代表全对，漏记、重记、记反方向都可能查不出。"),
    ("权责发生制", "💡 记忆口诀：权责发生制 = 不管钱收没收到，权利责任发生就记账。收付实现制才看「钱动没动」。"),
    ("谨慎性", "💡 记忆口诀：谨慎性 = 「不高估资产，不低估负债」。宁可少报利润不可多报，坏消息早报好消息晚报。"),
    ("实质重于形式", "💡 记忆口诀：实质重于形式 = 看经济实质不看法律形式。售后回购法律上卖了，经济上还是自己的，不确认收入。"),
    ("会计等式", "💡 记忆口诀：资产 = 负债 + 所有者权益。左边是「家底」，右边是「谁提供的」。永恒等式，复式记账的基础。"),
    ("配比原则", "💡 记忆口诀：配比 = 收入和对应成本同期确认。赚了钱同时记花了多少，不能只记收入不记成本。"),
]


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


def _extract_formula_and_result(explanation: str) -> tuple[str, str]:
    """从含「=」的计算型解析中提取文字公式与数值结果。

    解析常见形态如「销项税额=不含税销售额×适用税率=50×13%=6.5万元。」
    返回 ("销项税额=不含税销售额×适用税率", "6.5万元")：
    - 文字公式：等号左侧由汉字/运算符构成、不以数字开头的段落拼接；
    - 数值结果：最后一个以数字（含负号）开头的段落，去掉句末标点。
    无法提取时返回 ("", "")。
    """
    for line in explanation.splitlines():
        if "=" not in line:
            continue
        parts = [p.strip() for p in line.split("=") if p.strip()]
        text_parts: list[str] = []
        result = ""
        for p in parts:
            # 以数字（含负号）开头视为数值代入段，最后一个数值段即结果
            if re.match(r"^-?\d", p):
                result = p
            elif not result:
                # 尚未进入数值段，归入文字公式
                text_parts.append(p)
        if not text_parts:
            continue
        formula = "=".join(text_parts)
        result = result.rstrip("。.，,；;！!？?）)】】")
        return formula, result
    return "", ""


def _extract_first_sentence(text: str) -> str:
    """提取文本的首句实质内容，跳过「该说法错误/正确」等通用前缀。"""
    if not text:
        return ""
    s = text.strip()
    for prefix in ("该说法错误。", "该说法正确。", "该说法不正确。", "该说法错误，", "该说法正确，", "该说法不正确，",
                   "该说法错误", "该说法正确", "该说法不正确",
                   "此说法错误。", "此说法正确。", "此说法不正确。"):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
            break
    for sep in ("。", "；", ";", "！", "!", "？", "?", "\n"):
        if sep in s:
            s = s.split(sep)[0]
            break
    return s.strip("，,。.；;：: ")


def _extract_key_concept(content: str) -> str:
    """从题干中提取关键概念名词，用于概念题的通俗解释。"""
    if not content:
        return ""
    # 优先提取书名号/引号/方括号包裹的专有名词
    m = re.search(r"[「『《【\[]([^」』》】\]]{2,20})[」』》】\]]", content)
    if m:
        return m.group(1)
    # 「关于X，下列…」句式
    m = re.search(r"关于(.{2,20}?)[，,]", content)
    if m:
        return m.group(1)
    # 「X属于…」「X是指…」句式
    m = re.search(r"^([\u4e00-\u9fff·]{2,20}?)(?:属于|是指|称为)", content)
    if m:
        return m.group(1)
    # 兜底：取首个标点前的短句
    for sep in ("，", "。", "（", "(", "："):
        if sep in content:
            seg = content.split(sep)[0]
            if 2 <= len(seg) <= 20:
                return seg
            break
    return ""


def _question_type_desc(qtype: str) -> str:
    """题型的人类可读描述。"""
    return {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "judgment": "判断题",
        "tbs": "综合题",
        "journal_entry": "会计分录题",
    }.get(qtype, "题目")


def _is_calculation(q: Question) -> bool:
    """判断是否为计算型题目：解析中含「=」且能提取出文字公式。"""
    explanation = q.explanation or ""
    if "=" not in explanation:
        return False
    formula, _ = _extract_formula_and_result(explanation)
    return bool(formula)


def _question_anchor(q: Question) -> str:
    """生成题目专属的简洁锚点，用于区分同知识点/同关键词下的不同题目。

    优先级：计算题取「公式+结果」+题干数值 > 解析首句要点+题干数值 > 题干关键概念+数值。
    返回不含句末标点的短语，无法提取时返回空串。
    """
    explanation = q.explanation or ""
    content = q.content or ""
    key_nums = _extract_key_numbers(content)

    if "=" in explanation:
        formula, result = _extract_formula_and_result(explanation)
        if formula and result:
            base = f"公式为「{formula}」，结果{result}"
            if key_nums:
                return f"{base}，已知{key_nums}"
            return base
        if formula:
            return f"公式为「{formula}」"
    first = _extract_first_sentence(explanation)
    if first:
        if key_nums:
            return f"要点为「{first}」，涉及{key_nums}"
        return f"要点为「{first}」"
    concept = _extract_key_concept(content)
    if concept:
        if key_nums:
            return f"围绕「{concept}」，涉及{key_nums}"
        # 无数值时用题干片段
        snippet = content[:15].replace("（", "").replace("）", "").strip()
        return f"题干「{snippet}」"
    return ""


def _extract_key_numbers(content: str) -> str:
    """从题干中提取关键数值（如金额、百分比、年份），用于差异化重复内容。"""
    if not content:
        return ""
    # 提取所有数值（含万元/元/%等单位）
    numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(万元|元|%|件|个|股|天|月|年|次|人|笔|期|度)?', content)
    if not numbers:
        return ""
    # 取前3个有意义的数值
    result = []
    for num, unit in numbers[:3]:
        if unit:
            result.append(f"{num}{unit}")
        else:
            result.append(num)
    return "、".join(result)


def _build_simple_explanation(q: Question) -> str:
    """基于题目具体内容生成一句话通俗解释。

    策略优先级：计算题提公式+结果 > 判断题提首句要点 > 概念题提关键概念+数值 >
    兜底用知识点名称+题型描述。确保每条解释都包含题目特定信息（数值/公式/概念名）。
    """
    explanation = q.explanation or ""
    kp = q.knowledge_point
    kp_name = kp.name if kp else "本题考点"
    content = q.content or ""

    # 1. 计算题：提取文字公式 + 数值结果
    if "=" in explanation:
        formula, result = _extract_formula_and_result(explanation)
        if formula and result:
            # 追加题干数值以区分同公式同结果的题目
            key_nums = _extract_key_numbers(content)
            if key_nums:
                return f"核心公式：{formula}，本题结果为{result}（已知{key_nums}）。"
            return f"核心公式：{formula}，本题结果为{result}。"
        if formula:
            return f"核心公式：{formula}。"

    # 2. 判断题：取解析首句作为判断要点
    if q.question_type == "judgment":
        first = _extract_first_sentence(explanation)
        if first:
            result = f"判断要点：{first}。"
            # 过短时补充知识点上下文
            if len(result) < 15 and kp_name:
                result = f"判断要点：{first}（{kp_name}）。"
            return result

    # 3. 概念题：题干关键概念 + 题干数值 + 知识点名称
    concept = _extract_key_concept(content)
    key_nums = _extract_key_numbers(content)
    if concept and concept != kp_name:
        if key_nums:
            return f"本题核心：{kp_name}——{concept}（涉及{key_nums}）。"
        # 无数值时用题干前20字作为差异化因子
        snippet = content[:20].replace("（", "").replace("）", "").strip()
        return f"本题核心：{kp_name}——{snippet}。"
    kp_desc = (kp.description if kp else "") or ""
    desc_core = _extract_first_sentence(kp_desc)
    if desc_core.startswith(kp_name + "："):
        desc_core = desc_core[len(kp_name) + 1:]
    if desc_core:
        if key_nums:
            return f"本题核心：{kp_name}——{desc_core}（涉及{key_nums}）。"
        return f"本题核心：{kp_name}——{desc_core}。"

    # 4. 兜底：知识点名称 + 题型描述（仍随知识点不同而不同）
    return f"本题考查「{kp_name}」（{_question_type_desc(q.question_type)}），理解原理即可作答。"


# 知识点专属 fallback 口诀的科目风格修饰
_SUBJECT_MNEMONIC_STYLE: dict[str, str] = {
    "会计": "借贷方向先定准，再配平金额",
    "审计": "围绕「获取充分适当审计证据」展开",
    "财务成本": "公式先理解经济含义再记符号",
    "财务成本管理": "公式先理解经济含义再记符号",
    "公司战略": "先套框架要素，再记适用场景",
    "公司战略与风险管理": "先套框架要素，再记适用场景",
    "经济法": "圈出「应当/不得/可以」与数字要件",
    "税法": "抓住「计税依据×税率」的主线",
}

# 科目针对性的学习提示（叠加在难度/题型建议之后）
_SUBJECT_STUDY_HINT: dict[str, str] = {
    "会计": "建议画T型账户辅助分析，分录对了金额自然对",
    "审计": "审计语言要规范，区分「应当/可以/适当」的考试含义",
    "财务成本": "建议自制公式卡片，标注符号含义与适用条件",
    "财务成本管理": "建议自制公式卡片，标注符号含义与适用条件",
    "公司战略": "善用框架分析，理论结合案例缺一不可",
    "公司战略与风险管理": "善用框架分析，理论结合案例缺一不可",
    "经济法": "数字考点列表对比记忆，混淆率最高",
    "税法": "注意「含税/不含税」转换，这是计算第一步",
}


def _build_fallback_mnemonic(q: Question) -> str:
    """为未命中关键词规则的题目生成知识点专属、且含题目锚点的记忆口诀。

    结合知识点名称、科目风格、题型记忆方向、难度建议，并嵌入从解析中
    提取的题目专属锚点（公式/结果/首句要点），确保不同题目口诀各异，
    不同知识点口诀自然不同。
    """
    kp = q.knowledge_point
    kp_name = kp.name if kp else "本考点"
    subject = kp.subject if kp else ""
    style = _SUBJECT_MNEMONIC_STYLE.get(subject, "理解原理比死记硬背更有效")

    # 题型记忆方向
    is_calc = _is_calculation(q)
    if q.question_type == "judgment":
        direction = "判断题记规则边界与例外"
    elif is_calc:
        direction = "计算题先背公式再代数"
    elif q.question_type == "multiple_choice":
        direction = "多选题记要素清单防漏选"
    else:
        direction = "概念题抓定义关键词"

    # 难度建议
    diff = q.difficulty or 3
    if diff <= 2:
        diff_advice = "基础难度，多读两遍即可掌握"
    elif diff == 3:
        diff_advice = "中等难度，建议动手练一遍"
    else:
        diff_advice = "较高难度，需对比易错点"

    # 题目专属锚点：最大化口诀独特性（计算题取公式+结果，其余取解析首句）
    anchor = _question_anchor(q)
    anchor = f"锚点：{anchor}" if anchor else ""

    if anchor:
        return f"记「{kp_name}」：{direction}，{style}；{anchor}；{diff_advice}。"
    return f"记「{kp_name}」：{direction}，{style}；{diff_advice}。"


def _build_study_tip(q: Question) -> str:
    """基于难度、题型、知识点生成个性化学习小贴士。

    难度决定练习强度，题型决定做题方法，知识点名称保证建议具体可落地，
    科目提示补充针对性技巧。组合后可产生远超100种变体。
    """
    kp = q.knowledge_point
    kp_name = kp.name if kp else "本知识点"
    subject = kp.subject if kp else ""
    diff = q.difficulty or 3

    # 难度维度
    if diff <= 2:
        diff_tip = f"「{kp_name}」基础题，先把定义和原理弄懂，不必纠结细节"
    elif diff == 3:
        diff_tip = f"「{kp_name}」中等题，建议独立做一遍再对照解析，重点练应用"
    else:
        diff_tip = f"「{kp_name}」难题，建议整理易错点、对比相似考点后综合分析"

    # 题型维度
    is_calc = _is_calculation(q)
    if q.question_type == "judgment":
        type_tip = "判断题要圈出「应当/不得/可以/必须」等关键词，一字之差结论相反"
    elif is_calc:
        type_tip = "计算题先默写公式再代入数字，注意单位换算（万元/元、年/月），公式对就能拿步骤分"
    elif q.question_type == "multiple_choice":
        type_tip = "多选题注意「包括哪些/不包括」的问法，宁可少选不可错选"
    elif q.question_type == "tbs":
        type_tip = "综合题要分步拆解，先定知识点再逐问作答，避免一步到位"
    else:
        type_tip = "概念题用排除法更稳妥，注意选项间的细微差别"

    parts = [diff_tip, type_tip]
    hint = _SUBJECT_STUDY_HINT.get(subject)
    if hint:
        parts.append(hint)
    advice = "；".join(parts) + "。"
    # 追加题目专属锚点+题干摘要，确保小贴士随题目不同而不同
    anchor = _question_anchor(q)
    # 从题干提取交易类型（前15字）作为额外差异化因子
    snippet = (q.content or "")[:15].replace("（", "").replace("）", "").strip()
    if anchor and snippet:
        return f"本题{anchor}（{snippet}…）。{advice}"
    elif anchor:
        return f"本题{anchor}。{advice}"
    elif snippet:
        return f"题干「{snippet}…」。{advice}"
    return advice


def _enhance_explanations(db: Session) -> int:
    """
    为每道题生成四个解析模块：
    1. explanation        — 详细解析（保留原有内容，清除旧版混入的提示行）
    2. simple_explanation — 通俗易懂简洁解释（基于题目具体内容生成，非通用模板）
    3. mnemonic           — 记忆口诀/记忆诀窍（优先 _MNEMONIC_RULES 关键词匹配，
                            未命中则生成知识点专属且含题目锚点的口诀）
    4. study_tip          — 小贴士（按难度/题型/知识点个性化生成，变体丰富）

    重写目的：将三个模块的重复率从 99%+ 降至 50% 以下，每条文本均包含
    题目特定信息（数值、公式、概念名或解析要点），杜绝「同科目共用一句话」。
    """
    # 先为空知识点补充基础题目
    _fill_empty_knowledge_points(db)

    # 标注历年真题、考点
    _tag_exam_info(db)

    questions = db.query(Question).all()
    count = 0

    for q in questions:
        # 1. 清理 explanation：移除旧版混入的 💡 行
        if q.explanation and "💡" in q.explanation:
            lines = q.explanation.split("\n")
            q.explanation = "\n".join(l for l in lines if "💡" not in l).rstrip()

        if not q.explanation:
            continue

        # 2. 生成 simple_explanation（通俗易懂简洁解释）：基于题目具体内容
        q.simple_explanation = _build_simple_explanation(q)

        # 3. 生成 mnemonic（记忆口诀）：优先关键词匹配，未命中则知识点专属口诀
        match_text = (q.content or "") + " " + (q.explanation or "")
        best_mnemonic = None
        for keyword, mnemonic in _MNEMONIC_RULES:
            if keyword in match_text:
                # 去掉前缀 "💡 记忆口诀：" 只保留口诀内容
                best_mnemonic = mnemonic.replace("💡 记忆口诀：", "").replace("💡 ", "")
                break
        if best_mnemonic:
            # 保留匹配到的口诀原文（不变），追加题目专属锚点以消除
            # 同关键词题目共用同一口诀导致的重复
            anchor = _question_anchor(q)
            q.mnemonic = best_mnemonic if not anchor else f"{best_mnemonic} ｜ 本题{anchor}"
        else:
            q.mnemonic = _build_fallback_mnemonic(q)

        # 4. 生成 study_tip（小贴士）：按难度/题型/知识点个性化生成
        q.study_tip = _build_study_tip(q)

        count += 1

    return count

