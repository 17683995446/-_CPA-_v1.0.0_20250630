"""
CPA 大规模题库生成器。

策略：通过参数化模板 + 组合插槽值，批量生成 5000+ 道唯一题目。
每个模板定义题干结构，插槽组合产生不同数值/场景的题目变体。

生成分布：
- 会计：~1000 题
- 审计：~800 题
- 财务成本管理：~1000 题
- 公司战略与风险管理：~700 题
- 经济法：~800 题
- 税法：~700 题
"""
import itertools
import random
from typing import Callable

from sqlalchemy.orm import Session

from app.models import KnowledgePoint, Question, QuestionOption


# ========== 工具函数 ==========

def _ensure_kp(db: Session, code: str, name: str, subject: str, chapter: str,
               desc: str, difficulty: int) -> int:
    """确保知识点存在，返回 ID。"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.code == code).first()
    if kp:
        return kp.id
    kp = KnowledgePoint(
        code=code, name=name, subject=subject, chapter=chapter,
        description=desc, difficulty=difficulty,
    )
    db.add(kp)
    db.flush()
    return kp.id


def _add_question(
    db: Session, kp_id: int, q_type: str, content: str, answer: str,
    explanation: str, difficulty: int, source: str,
    options: list[tuple[str, str, bool]],
) -> None:
    """添加一道题目（跳过已存在的）。"""
    existing = db.query(Question).filter(
        Question.knowledge_point_id == kp_id,
        Question.content == content,
    ).first()
    if existing:
        return

    q = Question(
        knowledge_point_id=kp_id,
        question_type=q_type,
        content=content,
        answer=answer,
        explanation=explanation,
        difficulty=difficulty,
        source=source,
    )
    db.add(q)
    db.flush()
    for label, opt_content, is_correct in options:
        db.add(QuestionOption(
            question_id=q.id, label=label, content=opt_content, is_correct=is_correct,
        ))


def _gen_single_choice(
    content: str, answer: str, explanation: str,
    difficulty: int, options: list[tuple[str, str]],
) -> tuple[str, str, str, int, list[tuple[str, str, bool]]]:
    """构造单选题。options 是 (label, content) 列表，answer 即正确选项标签。

    会自动打乱选项顺序，确保正确答案不总是第一个。
    """
    import random as _r
    labels = ["A", "B", "C", "D", "E", "F"]
    # 将正确答案与干扰项分离
    correct_opts = [(l, c) for l, c in options if l == answer]
    wrong_opts = [(l, c) for l, c in options if l != answer]
    # 合并并打乱
    all_opts = correct_opts + wrong_opts
    _r.shuffle(all_opts)
    # 重新分配标签 A/B/C/D...
    shuffled = []
    new_answer = None
    for i, (orig_label, c) in enumerate(all_opts):
        new_label = labels[i]
        # 通过原始标签判断是否为正确选项（可靠，不依赖位置）
        is_correct = (orig_label == answer)
        if is_correct:
            new_answer = new_label
        shuffled.append((new_label, c, is_correct))
    # 确保 new_answer 被设置
    if new_answer is None and correct_opts:
        new_answer = labels[0]
    return ("single_choice", content, new_answer or answer, explanation, difficulty, shuffled)


def _gen_judgment(
    content: str, is_correct: bool, explanation: str, difficulty: int = 2,
) -> tuple[str, str, str, int, list[tuple[str, str, bool]]]:
    """构造判断题。"""
    answer = "正确" if is_correct else "错误"
    opts = [("A", "正确", is_correct), ("B", "错误", not is_correct)]
    return ("judgment", content, answer, explanation, difficulty, opts)


# ========== 会计科目题目生成 ==========

def gen_accounting(db: Session, kps: dict[str, int]) -> int:
    """生成会计科目题目，返回生成数量。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 借贷记账法：偿还款项（组合 amount × 场景）---
    scenarios = [
        ("短期借款", "银行存款", "偿还短期借款", "负债减少记借方，资产减少记贷方"),
        ("应付账款", "银行存款", "支付应付账款", "负债减少记借方，资产减少记贷方"),
        ("长期借款", "银行存款", "偿还长期借款", "负债减少记借方，资产减少记贷方"),
        ("应付票据", "银行存款", "支付应付票据款", "负债减少记借方，资产减少记贷方"),
        ("预收账款", "银行存款", "退回预收账款", "负债减少记借方，资产减少记贷方"),
    ]
    amounts = [10, 20, 50, 100, 200, 500, 800, 1000, 1500, 2000, 3000, 5000]
    for scen, amt in itertools.product(scenarios, amounts):
        acct_debit, acct_credit, desc, rule = scen
        content = f"企业用银行存款{desc}{amt}万元，下列会计处理正确的是（　）。"
        answer = f"借：{acct_debit} {amt}万元；贷：{acct_credit} {amt}万元"
        correct = f"借：{acct_debit} {amt}万元；贷：{acct_credit} {amt}万元"
        wrong1 = f"借：{acct_credit} {amt}万元；贷：{acct_debit} {amt}万元"
        wrong2 = f"借：{acct_debit} {amt}万元；贷：应付账款 {amt}万元"
        wrong3 = f"借：长期借款 {amt}万元；贷：{acct_credit} {amt}万元"
        opts = list(zip(labels, [correct, wrong1, wrong2, wrong3]))
        result = _gen_single_choice(content, "A", f"{rule}。{desc}{amt}万元，{answer}。", 3, opts)
        _add_question(db, kps["ACC-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 2. 存货初始计量（组合 买价 × 运费 × 挑选费）---
    prices = [50, 80, 100, 120, 150, 200, 250, 300, 400, 500]
    freights = [2, 3, 5, 8, 10, 12, 15]
    sort_fees = [1, 2, 3, 5]
    for price in prices:
        for freight in freights[:5]:
            for sort_fee in sort_fees[:3]:
                tax = round(price * 0.13, 1)
                total = price + freight + sort_fee
                content = f"某企业购入原材料一批，买价{price}万元，增值税进项税额{tax}万元，运输费{freight}万元，入库前挑选整理费{sort_fee}万元。该批材料的入账价值为（　）万元。"
                opts_data = [
                    ("A", str(total), True),
                    ("B", str(round(price + tax, 1)), False),
                    ("C", str(price), False),
                    ("D", str(round(price + tax + freight + sort_fee, 1)), False),
                ]
                _add_question(db, kps["ACC-03-01"], "single_choice", content, "A",
                              f"存货入账价值=买价+运输费+挑选整理费={price}+{freight}+{sort_fee}={total}万元，不含增值税。",
                              3, "mock", opts_data)
                count += 1

    # --- 3. 固定资产折旧（组合 原值 × 年限 × 方法）---
    origins = [50, 80, 100, 120, 150, 200, 300, 500]
    years = [3, 4, 5, 8, 10]
    residuals = [0.02, 0.03, 0.05]
    for origin in origins:
        for year in years:
            for res_rate in residuals:
                residual = round(origin * res_rate, 1)
                depreciable = origin - residual
                annual_dep = round(depreciable / year, 2)
                content = f"某企业一项固定资产原值{origin}万元，预计使用{year}年，预计净残值{residual}万元。采用年限平均法，年折旧额为（　）万元。"
                wrong_opts = [
                    round(origin / year, 2),
                    round(depreciable / (year - 1), 2) if year > 1 else round(depreciable, 2),
                    round((origin - residual * 2) / year, 2),
                ]
                # 确保干扰项不同
                all_opts = [(str(annual_dep), True)]
                seen = {annual_dep}
                for w in wrong_opts:
                    if w not in seen:
                        all_opts.append((str(w), False))
                        seen.add(w)
                    if len(all_opts) == 4:
                        break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(annual_dep + random.uniform(-5, 5), 2)
                    if fake not in seen and fake > 0:
                        all_opts.append((str(fake), False))
                        seen.add(fake)
                labels_4 = ["A", "B", "C", "D"]
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["ACC-04-02"], "single_choice", content, "A",
                              f"年折旧额=(原值-净残值)/年限=({origin}-{residual})/{year}={annual_dep}万元。",
                              3, "mock", opts_data)
                count += 1

    # --- 4. 会计要素判断题 ---
    judgments = [
        ("资产=负债+所有者权益是编制资产负债表的理论基础。", True, "资产负债表左右两侧必须相等。"),
        ("收入-费用=利润是编制利润表的理论基础。", True, "利润表反映一定期间的经营成果。"),
        ("所有者权益增加一定意味着企业获得了利润。", False, "所有者权益增加也可能是股东追加投资。"),
        ("负债减少一定会导致资产减少。", False, "负债减少也可能导致所有者权益减少（如债转股）。"),
        ("资产减值损失一经确认不得转回。", False, "只有部分资产（如长期资产）减值不得转回，存货跌价准备可以转回。"),
        ("企业发生的借款费用都应当资本化。", False, "只有符合资本化条件的借款费用才能资本化，其余费用化。"),
        ("无形资产摊销一律计入管理费用。", False, "无形资产摊销根据用途计入不同科目。"),
        ("商业折扣不影响应收账款的入账价值。", True, "商业折扣在销售时已扣除，不入账。"),
        ("现金折扣不影响应收账款的入账价值。", True, "现金折扣在实际发生时计入财务费用（总价法）。"),
        ("存货采用先进先出法，在物价上涨时会高估利润。", True, "先进先出法用早期低成本匹配当期收入，利润偏高。"),
    ]
    for content, is_correct, explanation in judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["ACC-01-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 5. 收入确认金额计算 ---
    for unit_price in [100, 200, 500, 1000]:
        for qty in [10, 20, 50, 100]:
            for discount in [0, 0.05, 0.10]:
                revenue = round(unit_price * qty * (1 - discount), 1)
                disc_text = f"，商业折扣{int(discount*100)}%" if discount > 0 else ""
                content = f"某企业销售产品{qty}件，单价{unit_price}元{disc_text}。确认的收入金额为（　）元。"
                opts_data = [
                    ("A", str(revenue), True),
                    ("B", str(unit_price * qty), False),
                    ("C", str(round(unit_price * qty * (1 + 0.13), 1)), False),
                    ("D", str(round(revenue * 0.87, 1)), False),
                ]
                _add_question(db, kps["ACC-16-01"], "single_choice", content, "A",
                              f"收入=单价×数量×(1-折扣)={unit_price}×{qty}×{1-discount}={revenue}元。",
                              3, "mock", opts_data)
                count += 1

    return count


# ========== 审计科目题目生成 ==========

def gen_auditing(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 审计证据：充分性 vs 适当性判断题 ---
    audit_judgments = [
        ("审计证据的充分性是对审计证据数量的衡量。", True, "充分性指数量。"),
        ("审计证据的适当性是对审计证据质量的衡量。", True, "适当性=相关性+可靠性。"),
        ("审计证据的可靠性不受其来源的影响。", False, "外部证据比内部证据更可靠。"),
        ("审计证据的数量越多，审计质量就越高。", False, "质量（适当性）同样重要。"),
        ("书面证据比口头证据更可靠。", True, "书面证据有记录可查。"),
        ("从原件获取的审计证据比从传真件获取的更可靠。", True, "原件不易被篡改。"),
        ("审计证据的相关性是指其与审计目标的关系。", True, "相关性是适当性的维度之一。"),
        ("审计程序的性质影响审计证据的充分性。", False, "性质影响适当性，数量影响充分性。"),
    ]
    for content, is_correct, explanation in audit_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["AUD-06-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 2. 审计程序选择 ---
    procedures = [
        ("检查记录或文件", "审查书面记录"),
        ("检查有形资产", "盘点实物资产"),
        ("观察", "查看他人执行的过程"),
        ("询问", "以书面或口头方式获取信息"),
        ("函证", "向第三方获取书面确认"),
        ("重新计算", "验证计算的准确性"),
        ("重新执行", "独立重新执行被审计单位的程序"),
        ("分析程序", "通过关系比较分析数据"),
    ]
    scenarios = [
        ("验证银行存款余额", "函证", "向银行函证最可靠"),
        ("验证应收账款余额", "函证", "向债务人函证"),
        ("验证存货存在性", "检查有形资产", "实地盘点"),
        ("验证固定资产存在性", "检查有形资产", "实地查看"),
        ("验证工资计算准确性", "重新计算", "独立验算"),
        ("验证内部控制运行有效性", "重新执行", "独立重新执行"),
        ("验证收入的合理性", "分析程序", "通过趋势分析"),
        ("验证仓库管理流程", "观察", "现场观察操作"),
        ("验证凭证记录完整性", "检查记录或文件", "审查凭证"),
        ("了解管理层对风险的评估", "询问", "与管理层沟通"),
    ]
    for scenario, correct_proc, reason in scenarios:
        for proc_name, proc_desc in procedures:
            if proc_name == correct_proc:
                continue
            content = f"注册会计师要{scenario}，最适宜的审计程序是（　）。"
            correct = correct_proc
            wrong1 = proc_name
            # 取另外两个程序作为干扰
            other_procs = [p[0] for p in procedures if p[0] not in (correct_proc, proc_name)][:2]
            opts = list(zip(labels, [correct, wrong1, other_procs[0], other_procs[1]]))
            result = _gen_single_choice(content, "A", f"{reason}。", 3, opts)
            _add_question(db, kps["AUD-03-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    # --- 3. 审计风险模型 ---
    inherent_risks = [0.5, 0.6, 0.7, 0.8, 0.9]
    control_risks = [0.3, 0.4, 0.5, 0.6, 0.7]
    acceptable_aud_risks = [0.05, 0.10, 0.15]
    for ir in inherent_risks:
        for cr in control_risks:
            for ar in acceptable_aud_risks:
                rmm = round(ir * cr, 4)
                dr = round(ar / rmm, 4) if rmm > 0 else 0
                content = f"在审计风险模型中，审计风险为{ar}，重大错报风险为{rmm}，则检查风险为（　）。"
                wrong_opts = [
                    round(ar * rmm, 4),
                    round(ar + rmm, 4),
                    round(ar - rmm, 4) if ar > rmm else round(rmm - ar, 4),
                ]
                all_opts = [(str(dr), True)]
                seen = {dr}
                for w in wrong_opts:
                    if w not in seen:
                        all_opts.append((str(w), False))
                        seen.add(w)
                    if len(all_opts) == 4:
                        break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(dr + random.uniform(-0.1, 0.1), 4)
                    if fake not in seen and fake > 0:
                        all_opts.append((str(fake), False))
                        seen.add(fake)
                labels_4 = ["A", "B", "C", "D"]
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["AUD-06-02"], "single_choice", content, "A",
                              f"检查风险=审计风险/重大错报风险={ar}/{rmm}={dr}。",
                              4, "mock", opts_data)
                count += 1

    # --- 4. 内部控制要素 ---
    ic_elements = [
        ("控制环境", "治理层和管理层的态度与行动"),
        ("风险评估", "识别和分析风险"),
        ("控制活动", "有助于确保管理层指令得以执行的政策和程序"),
        ("信息与沟通", "确保信息识别、获取和传递"),
        ("监控", "评估内部控制系统在一定时期内运行质量的过程"),
    ]
    ic_questions = [
        ("下列各项中，属于内部控制要素的是", True, "五要素之一"),
        ("下列各项中，不属于内部控制要素的是", False, "非内部控制五要素"),
    ]
    non_ic = ["投资决策", "利润分配", "市场推广", "产品定价", "品牌战略", "供应链设计"]
    for elem_name, elem_desc in ic_elements:
        # 正向：选择属于的
        for non in non_ic[:3]:
            other_elems = [e[0] for e in ic_elements if e[0] != elem_name][:3]
            all_wrong = [non] + other_elems[:2]
            opts = list(zip(labels, [elem_name] + all_wrong))
            content = f"下列各项中，属于内部控制要素「{elem_desc}」的是（　）。"
            result = _gen_single_choice(content, "A", f"{elem_name}是内部控制五要素之一。", 3, opts)
            _add_question(db, kps["AUD-07-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    # --- 5. 审计概念判断 ---
    concept_judgments = [
        ("审计的目的是提高财务信息的可信度。", True, "审计为财务信息提供合理保证。"),
        ("合理保证意味着绝对保证。", False, "合理保证是高水平的保证，但非绝对。"),
        ("审计意见旨在提高财务报表的可信度。", True, "审计意见增强报表使用者对报表的信任。"),
        ("审计仅限于财务报表审计。", False, "审计还包括内部控制审计、合规审计等。"),
        ("注册会计师应当保持独立性。", True, "独立性是审计的基本要求。"),
        ("审计准则具有强制性。", True, "注册会计师必须遵守审计准则。"),
        ("审计风险是可以消除的。", False, "审计风险只能降低不能消除。"),
    ]
    for content, is_correct, explanation in concept_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["AUD-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


# ========== 财务成本管理题目生成 ==========

def gen_finance(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 复利终值 F=P(1+i)^n ---
    principals = [1000, 5000, 10000, 20000, 50000, 100000]
    rates = [0.03, 0.05, 0.06, 0.08, 0.10]
    years_list = [1, 2, 3, 5, 10]
    for p in principals:
        for r in rates:
            for n in years_list:
                fv = round(p * (1 + r) ** n)
                content = f"某人现在存入银行{p}元，年利率{int(r*100)}%，复利计息，{n}年后的本利和为（　）元。"
                wrong_opts = [
                    round(p * (1 + r * n)),  # 单利
                    round(p * (1 + r) ** (n + 1)),
                    round(p + p * r * n * 1.5),
                ]
                all_opts = [(str(fv), True)]
                seen = {fv}
                for w in wrong_opts:
                    if w not in seen:
                        all_opts.append((str(w), False))
                        seen.add(w)
                    if len(all_opts) == 4:
                        break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(fv + random.uniform(-fv*0.2, fv*0.2))
                    if fake not in seen and fake > 0:
                        all_opts.append((str(fake), False))
                        seen.add(fake)
                labels_4 = ["A", "B", "C", "D"]
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["FCM-01-03"], "single_choice", content, "A",
                              f"复利终值F=P×(1+i)^n={p}×(1+{r})^{n}={fv}元。",
                              3, "mock", opts_data)
                count += 1

    # --- 2. 复利现值 P=F/(1+i)^n ---
    future_values = [1100, 1500, 2000, 5000, 10000, 20000, 50000]
    rates_pv = [0.03, 0.05, 0.08, 0.10]
    years_pv = [1, 2, 3, 5]
    for fv in future_values:
        for r in rates_pv:
            for n in years_pv:
                pv = round(fv / (1 + r) ** n, 2)
                content = f"某人希望在{n}年后获得{fv}元，年利率{int(r*100)}%，复利计息，现在应存入（　）元。"
                wrong_opts = [
                    round(fv / (1 + r * n), 2),
                    round(fv * (1 + r) ** n, 2),
                    round(fv / (1 + r) ** (n - 1), 2) if n > 1 else round(fv / (1 + r), 2),
                ]
                all_opts = [(str(pv), True)]
                seen = {pv}
                for w in wrong_opts:
                    if w not in seen:
                        all_opts.append((str(w), False))
                        seen.add(w)
                    if len(all_opts) == 4:
                        break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(pv + random.uniform(-pv*0.3, pv*0.3), 2)
                    if fake not in seen and fake > 0:
                        all_opts.append((str(fake), False))
                        seen.add(fake)
                labels_4 = ["A", "B", "C", "D"]
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["FCM-01-03"], "single_choice", content, "A",
                              f"复利现值P=F/(1+i)^n={fv}/(1+{r})^{n}={pv}元。",
                              3, "mock", opts_data)
                count += 1

    # --- 3. 年金终值 ---
    for pmt in [100, 500, 1000, 2000, 5000]:
        for r in [0.03, 0.05, 0.08, 0.10]:
            for n in [3, 5, 10, 15, 20]:
                fv_annuity = round(pmt * ((1 + r) ** n - 1) / r, 2)
                content = f"某人每年末存入{pmt}元，年利率{int(r*100)}%，复利计息，{n}年后的年金终值为（　）元。"
                wrong_opts = [
                    round(pmt * n, 2),
                    round(pmt * (1 + r) ** n, 2),
                    round(pmt * ((1 + r) ** (n + 1) - 1) / r, 2),
                ]
                all_opts = [(str(fv_annuity), True)]
                seen = {fv_annuity}
                for w in wrong_opts:
                    if w not in seen:
                        all_opts.append((str(w), False))
                        seen.add(w)
                    if len(all_opts) == 4:
                        break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(fv_annuity + random.uniform(-fv_annuity*0.2, fv_annuity*0.2), 2)
                    if fake not in seen and fake > 0:
                        all_opts.append((str(fake), False))
                        seen.add(fake)
                labels_4 = ["A", "B", "C", "D"]
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["FCM-01-03"], "single_choice", content, "A",
                              f"年金终值F=A×[(1+i)^n-1]/i={pmt}×[(1+{r})^{n}-1]/{r}={fv_annuity}元。",
                              4, "mock", opts_data)
                count += 1

    # --- 4. 资本成本 WACC ---
    debt_costs = [0.04, 0.05, 0.06, 0.08]
    equity_costs = [0.08, 0.10, 0.12, 0.15]
    debt_ratios = [0.3, 0.4, 0.5, 0.6]
    tax_rates = [0.15, 0.25]
    for rd in debt_costs:
        for re in equity_costs:
            for wd in debt_ratios:
                for t in tax_rates:
                    we = 1 - wd
                    wacc = round(rd * (1 - t) * wd + re * we, 4)
                    content = f"某企业债务资本成本{int(rd*100)}%，权益资本成本{int(re*100)}%，债务占比{int(wd*100)}%，企业所得税税率{int(t*100)}%。该企业的WACC为（　）。"
                    wrong_opts = [
                        round(rd * wd + re * we, 4),
                        round(rd * (1 - t) * we + re * wd, 4),
                        round((rd + re) / 2, 4),
                    ]
                    all_opts = [(f"{wacc*100:.1f}%", True)]
                    seen = {f"{wacc*100:.1f}%"}
                    for w in wrong_opts:
                        w_str = f"{w*100:.1f}%"
                        if w_str not in seen:
                            all_opts.append((w_str, False))
                            seen.add(w_str)
                        if len(all_opts) == 4:
                            break
                    _attempts = 0
                    while len(all_opts) < 4 and _attempts < 200:
                        _attempts += 1
                        fake = round(wacc + random.uniform(-0.02, 0.02), 4)
                        fake_str = f"{fake*100:.1f}%"
                        if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                            all_opts.append((fake_str, False))
                            seen.add(fake_str)
                    labels_4 = ["A", "B", "C", "D"]
                    opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                    _add_question(db, kps["FCM-03-01"], "single_choice", content, "A",
                                  f"WACC=Kd×(1-T)×Wd+Ke×We={rd}×(1-{t})×{wd}+{re}×{we}={wacc*100:.1f}%。",
                                  4, "mock", opts_data)
                    count += 1

    # --- 5. 盈亏平衡点 ---
    for price in [50, 80, 100, 150, 200, 300, 500]:
        for var_cost in [20, 30, 40, 60, 80, 100]:
            if var_cost >= price:
                continue
            for fixed_cost in [10000, 20000, 50000, 80000, 100000, 200000]:
                bep = round(fixed_cost / (price - var_cost))
                content = f"某产品单价{price}元，单位变动成本{var_cost}元，固定成本总额{fixed_cost}元。盈亏平衡点销售量为（　）件。"
                wrong_opts = [
                    round(fixed_cost / price),
                    round(fixed_cost / var_cost),
                    round(fixed_cost / (price - var_cost) * 0.8),
                ]
                all_opts = [(str(int(bep)), True)]
                seen = {int(bep)}
                for w in wrong_opts:
                    w_int = int(w)
                    if w_int not in seen:
                        all_opts.append((str(w_int), False))
                        seen.add(w_int)
                    if len(all_opts) == 4:
                        break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = int(bep + random.uniform(-bep*0.3, bep*0.3))
                    if fake not in seen and fake > 0:
                        all_opts.append((str(fake), False))
                        seen.add(fake)
                labels_4 = ["A", "B", "C", "D"]
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["FCM-14-01"], "single_choice", content, "A",
                              f"盈亏平衡点=固定成本/(单价-单位变动成本)={fixed_cost}/({price}-{var_cost})={int(bep)}件。",
                              3, "mock", opts_data)
                count += 1

    # --- 6. 风险与报酬判断题 ---
    risk_judgments = [
        ("系统性风险可以通过投资组合分散。", False, "系统性风险（市场风险）无法分散。"),
        ("非系统性风险可以通过投资组合分散。", True, "非系统性风险（特定风险）可分散。"),
        ("β系数衡量的是系统性风险。", True, "β反映个别资产相对市场的波动。"),
        ("β系数大于1表示该资产风险低于市场。", False, "β>1表示风险高于市场。"),
        ("β系数等于0表示该资产无风险。", True, "β=0的资产与市场无关。"),
        ("期望报酬率是各种可能报酬率的加权平均。", True, "以概率为权重的加权平均。"),
        ("标准差是衡量总风险的指标。", True, "标准差反映离散程度。"),
        ("资本资产定价模型（CAPM）用于计算必要报酬率。", True, "CAPM: E(R)=Rf+β×(Rm-Rf)。"),
    ]
    for content, is_correct, explanation in risk_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["FCM-01-03"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


# ========== 战略与风险管理题目生成 ==========

def gen_strategy(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. SWOT 矩阵战略选择 ---
    swot_strategies = [
        ("SO", "优势-机会", "增长型战略", "利用内部优势抓住外部机会"),
        ("WO", "劣势-机会", "扭转型战略", "利用外部机会克服内部劣势"),
        ("ST", "优势-威胁", "多元化战略", "利用内部优势规避外部威胁"),
        ("WT", "劣势-威胁", "防御型战略", "克服劣势规避威胁"),
    ]
    swot_scenarios = [
        ("企业拥有强大的研发能力，且市场需求增长", "SO", "研发是优势，需求增长是机会"),
        ("企业品牌知名度高，竞争对手进入市场", "ST", "品牌是优势，竞争是威胁"),
        ("企业资金不足，但政府出台扶持政策", "WO", "资金不足是劣势，扶持是机会"),
        ("企业技术落后，行业竞争激烈", "WT", "技术落后是劣势，竞争激烈是威胁"),
        ("企业拥有专利技术，海外市场开放", "SO", "专利是优势，海外市场是机会"),
        ("企业管理效率低，原材料价格上涨", "WT", "效率低是劣势，涨价是威胁"),
        ("企业销售渠道薄弱，电商兴起", "WO", "渠道薄弱是劣势，电商是机会"),
        ("企业产能充足，替代产品出现", "ST", "产能是优势，替代品是威胁"),
    ]
    for scenario, correct_type, reason in swot_scenarios:
        correct_strategy = [s for s in swot_strategies if s[0] == correct_type][0]
        wrong_strategies = [s for s in swot_strategies if s[0] != correct_type]
        for ws in wrong_strategies[:3]:
            other_two = [s for s in swot_strategies if s[0] not in (correct_type, ws[0])][:2]
            opts = list(zip(labels, [correct_strategy[2], ws[2], other_two[0][2], other_two[1][2]]))
            content = f"{scenario}，根据SWOT分析，企业应采取的战略类型是（　）。"
            result = _gen_single_choice(content, "A", f"{reason}，应采取{correct_strategy[2]}（{correct_strategy[3]}）。", 3, opts)
            _add_question(db, kps["STR-02-03"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    # --- 2. PEST 分析要素 ---
    pest_factors = [
        ("经济因素", "利率、汇率、经济增长率"),
        ("政治法律因素", "产业政策、法律法规"),
        ("社会文化因素", "人口结构、消费观念"),
        ("技术因素", "新技术、研发投入"),
    ]
    pest_scenarios = [
        ("央行调整利率", "经济因素"),
        ("政府出台行业新规", "政治法律因素"),
        ("人口老龄化加剧", "社会文化因素"),
        ("人工智能技术突破", "技术因素"),
        ("GDP增速放缓", "经济因素"),
        ("环保法规修订", "政治法律因素"),
        ("消费者偏好线上购物", "社会文化因素"),
        ("5G技术商用", "技术因素"),
        ("汇率大幅波动", "经济因素"),
        ("劳动法修订", "政治法律因素"),
    ]
    for scenario, correct_factor in pest_scenarios:
        wrong_factors = [f[0] for f in pest_factors if f[0] != correct_factor]
        for wf in wrong_factors[:2]:
            other_two = [f for f in pest_factors if f[0] not in (correct_factor, wf)][:2]
            opts = list(zip(labels, [correct_factor, wf, other_two[0][0], other_two[1][0]]))
            content = f"在PEST分析中，「{scenario}」属于（　）。"
            result = _gen_single_choice(content, "A", f"{scenario}属于{correct_factor}。", 2, opts)
            _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    # --- 3. 风险类型识别 ---
    risk_types = [
        ("战略风险", "战略决策失误"),
        ("运营风险", "日常运营问题"),
        ("财务风险", "资金流动性问题"),
        ("市场风险", "市场价格波动"),
        ("法律风险", "法律合规问题"),
    ]
    risk_scenarios = [
        ("企业进入不熟悉的新市场", "战略风险"),
        ("生产线设备故障导致停产", "运营风险"),
        ("企业无法按时偿还到期债务", "财务风险"),
        ("原材料价格大幅上涨", "市场风险"),
        ("企业因违反环保法被处罚", "法律风险"),
        ("并购后整合失败", "战略风险"),
        ("关键供应商突然中断供货", "运营风险"),
        ("汇率变动导致汇兑损失", "市场风险"),
        ("合同条款违法被法院撤销", "法律风险"),
        ("现金流断裂", "财务风险"),
        ("品牌定位失误", "战略风险"),
        ("员工罢工", "运营风险"),
        ("利率上升增加借款成本", "市场风险"),
        ("知识产权被侵权", "法律风险"),
        ("应收账款大量坏账", "财务风险"),
    ]
    for scenario, correct_type in risk_scenarios:
        wrong_types = [r[0] for r in risk_types if r[0] != correct_type][:3]
        opts = list(zip(labels, [correct_type] + wrong_types))
        content = f"下列情况中，属于{correct_type}的是（　）。"
        # 反过来问：哪个场景属于该风险类型
        wrong_scenarios = [s for s, t in risk_scenarios if t != correct_type][:3]
        opts2 = list(zip(labels, [scenario] + wrong_scenarios))
        result = _gen_single_choice(content, "A", f"{scenario}属于{correct_type}。", 3, opts2)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 4. 总体战略类型 ---
    strategy_types = [
        ("密集型战略", "市场渗透、市场开发、产品开发"),
        ("一体化战略", "前向一体化、后向一体化、横向一体化"),
        ("多元化战略", "相关多元化、非相关多元化"),
    ]
    strategy_scenarios = [
        ("企业加大现有产品的营销力度", "密集型战略", "市场渗透"),
        ("企业将产品销售到新的地区", "密集型战略", "市场开发"),
        ("企业开发新产品面向现有客户", "密集型战略", "产品开发"),
        ("企业收购其供应商", "一体化战略", "后向一体化"),
        ("企业收购其分销商", "一体化战略", "前向一体化"),
        ("企业收购同行业竞争对手", "一体化战略", "横向一体化"),
        ("企业进入相关行业", "多元化战略", "相关多元化"),
        ("企业进入完全无关的行业", "多元化战略", "非相关多元化"),
    ]
    for scenario, correct_type, detail in strategy_scenarios:
        wrong_types = [s[0] for s in strategy_types if s[0] != correct_type]
        opts = list(zip(labels, [correct_type] + wrong_types + [wrong_types[0] + "（其他）"]))
        # 确保4个不同选项
        opts_list = [(labels[i], opts[i][1], i == 0) for i in range(min(4, len(opts)))]
        while len(opts_list) < 4:
            opts_list.append((labels[len(opts_list)], "不确定", False))
        content = f"{scenario}，这属于（　）。"
        _add_question(db, kps["STR-05-01"], "single_choice", content, "A",
                      f"{scenario}属于{correct_type}中的{detail}。", 3, "mock", opts_list)
        count += 1

    return count


# ========== 经济法题目生成 ==========

def gen_law(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 公司法数字类 ---
    company_numbers = [
        ("有限责任公司的股东人数上限", "50", "50人以下", ["30", "100", "200"]),
        ("股份有限公司发起人人数下限", "2", "2-200人", ["1", "5", "10"]),
        ("股份有限公司发起人人数上限", "200", "2-200人", ["50", "100", "500"]),
        ("有限责任公司董事会成员人数（一般）", "3-13", "3到13人", ["3-5", "5-9", "5-19"]),
        ("有限责任公司监事会成员不少于", "3", "不少于3人", ["1", "2", "5"]),
        ("股东大会年会应当在每年召开", "1次", "每年一次", ["2次", "半年1次", "季度1次"]),
        ("公司解散后清算组应当自成立之日起多少日内通知债权人", "10日", "10日内通知", ["5日", "15日", "30日"]),
        ("债权人申报债权的期限自接到通知书之日起不少于", "30日", "不少于30日", ["15日", "45日", "60日"]),
        ("公司减资后的注册资本不得低于法定的最低限额，有限责任公司最低注册资本为", "3万元", "3万元", ["1万元", "5万元", "10万元"]),
        ("一人有限责任公司的注册资本最低限额为", "10万元", "10万元", ["3万元", "5万元", "20万元"]),
        ("股份有限公司注册资本最低限额为", "500万元", "500万元", ["100万元", "300万元", "1000万元"]),
        ("上市公司董事会成员不少于", "5人", "不少于5人", ["3人", "7人", "9人"]),
    ]
    for question, answer, reason, wrongs in company_numbers:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"根据《公司法》，{question}为（　）。"
        result = _gen_single_choice(content, "A", f"《公司法》规定{reason}。", 2, opts)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 2. 公司法判断题 ---
    law_judgments = [
        ("有限责任公司股东以其认缴的出资额为限对公司承担责任。", True, "有限责任原则。"),
        ("股份有限公司股东以其认购的股份为限对公司承担责任。", True, "有限责任原则。"),
        ("一人有限责任公司可以由自然人或法人设立。", True, "一人公司股东可以是自然人或法人。"),
        ("公司可以为股东提供担保。", True, "但需经股东会决议。"),
        ("公司法定代表人必须由董事长担任。", False, "可由董事长、执行董事或经理担任。"),
        ("公司合并应当自作出决议之日起10日内通知债权人。", False, "应在30日内通知债权人。"),
        ("股东有权查阅公司章程和股东会会议记录。", True, "股东知情权。"),
        ("公司分立前的债务由分立后的公司承担连带责任。", True, "除非另有约定。"),
        ("有限责任公司的股东之间可以相互转让其全部或部分股权。", True, "内部转让自由。"),
        ("股东向股东以外的人转让股权，应当经其他股东过半数同意。", True, "外部转让需过半数同意。"),
    ]
    for content, is_correct, explanation in law_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 3. 公司治理结构 ---
    governance = [
        ("决定公司的经营方针和投资计划", "股东会", "股东会职权"),
        ("决定公司的年度财务预算方案", "董事会", "董事会职权"),
        ("检查公司财务", "监事会", "监事会职权"),
        ("对董事、高级管理人员提起诉讼", "监事会", "监事会职权"),
        ("召集股东会会议", "董事会", "董事会职权"),
        ("选举和更换非由职工代表担任的董事", "股东会", "股东会职权"),
        ("决定公司内部管理机构的设置", "董事会", "董事会职权"),
        ("聘任或解聘公司经理", "董事会", "董事会职权"),
        ("组织实施公司年度经营计划", "经理", "经理职权"),
        ("制定公司的具体规章制度", "经理", "经理职权"),
    ]
    organs = ["股东会", "董事会", "监事会", "经理"]
    for func_name, correct_organ, reason in governance:
        wrong_organs = [o for o in organs if o != correct_organ]
        for wo in wrong_organs[:2]:
            other_two = [o for o in organs if o not in (correct_organ, wo)][:2]
            # 实际上应该是4个选项
            opts = list(zip(labels, [correct_organ, wo, other_two[0], other_two[1]]))
            content = f"根据《公司法》，{func_name}属于（　）的职权。"
            result = _gen_single_choice(content, "A", f"这是{correct_organ}的职权（{reason}）。", 3, opts)
            _add_question(db, kps["LAW-05-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1
            break  # 每个职权只生成1题

    # --- 4. 合同法判断题 ---
    contract_judgments = [
        ("要约到达受要约人时生效。", True, "到达生效原则。"),
        ("承诺通知到达要约人时生效。", True, "到达生效。"),
        ("要约可以撤回，撤回通知应在要约到达前到达。", True, "撤回条件。"),
        ("要约可以撤销，撤销通知应在受要约人发出承诺通知之前到达。", True, "撤销条件。"),
        ("承诺可以撤回，但不能撤销。", True, "承诺到达即生效，不可撤销。"),
        ("要约人确定了承诺期限的要约不得撤销。", True, "有期限的要约不可撤销。"),
        ("受要约人有理由认为要约不可撤销并已做准备，该要约不可撤销。", True, "信赖利益保护。"),
        ("承诺对要约的内容作出实质性变更的，为新要约。", True, "实质性变更构成新要约。"),
        ("合同自承诺生效时成立。", True, "承诺生效合同成立。"),
        ("采用格式条款订立合同的，提供格式条款的一方应遵循公平原则。", True, "格式条款公平原则。"),
        ("同时履行抗辩权适用于双务合同中双方义务无先后履行顺序的情形。", True, "同时履行抗辩权。"),
        ("先履行抗辩权适用于有先后履行顺序且先履行一方未履行的情形。", True, "先履行抗辩权。"),
        ("不安抗辩权适用于先履行一方有证据证明对方经营恶化。", True, "不安抗辩权。"),
        ("违约金过高的，当事人可以请求人民法院予以适当减少。", True, "违约金调整规则。"),
        ("定金的数额不得超过主合同标的额的20%。", True, "定金上限20%。"),
    ]
    for content, is_correct, explanation in contract_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["LAW-03-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 5. 合同法单选题 ---
    contract_questions = [
        ("要约的生效时间为", "到达受要约人时", "到达主义", ["发出时", "受要约人阅读时", "要约人发出后合理时间"]),
        ("承诺的生效时间为", "到达要约人时", "到达主义", ["发出时", "要约人阅读时", "受要约人发出后合理时间"]),
        ("定金的数额不得超过主合同标的额的", "20%", "法定上限", ["10%", "30%", "50%"]),
        ("违约金过分高于造成损失的，当事人可以请求", "适当减少", "违约金调整", ["增加", "取消", "不调整"]),
        ("合同保全的撤销权自债权人知道撤销事由之日起多长时间内行使", "1年", "撤销权时效", ["6个月", "2年", "5年"]),
        ("合同保全的撤销权自债务人的行为发生之日起多长时间内未行使则消灭", "5年", "最长保护期", ["1年", "3年", "10年"]),
        ("买卖合同中标的物毁损灭失的风险在交付前由谁承担", "出卖人", "交付前风险归出卖人", ["买受人", "双方共同", "保险公司"]),
        ("买卖合同中标的物毁损灭失的风险在交付后由谁承担", "买受人", "交付后风险归买受人", ["出卖人", "双方共同", "保险公司"]),
    ]
    for question, answer, reason, wrongs in contract_questions:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"{reason}。", 3, opts)
        _add_question(db, kps["LAW-03-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


# ========== 税法题目生成 ==========

def gen_tax(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 增值税销项税额计算 ---
    vat_rates = [13, 9, 6]
    revenues = [50, 100, 200, 300, 500, 800, 1000, 2000, 5000, 10000]
    for rate in vat_rates:
        for revenue in revenues:
            output_tax = round(revenue * rate / 100, 2)
            content = f"某一般纳税人企业销售货物取得不含税销售额{revenue}万元，适用税率{rate}%。增值税销项税额为（　）万元。"
            wrong_opts = [
                round(revenue * (rate - 1) / 100, 2),
                round(revenue * (rate + 1) / 100, 2),
                round(revenue * rate / 100 * 0.7, 2),
            ]
            all_opts = [(str(output_tax), True)]
            seen = {str(output_tax)}
            for w in wrong_opts:
                w_str = str(w)
                if w_str not in seen:
                    all_opts.append((w_str, False))
                    seen.add(w_str)
                if len(all_opts) == 4:
                    break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(output_tax + random.uniform(-output_tax*0.2, output_tax*0.2), 2)
                fake_str = str(fake)
                if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                    all_opts.append((fake_str, False))
                    seen.add(fake_str)
            labels_4 = ["A", "B", "C", "D"]
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, "A",
                          f"销项税额=不含税销售额×适用税率={revenue}×{rate}%={output_tax}万元。",
                          2, "mock", opts_data)
            count += 1

    # --- 2. 含税销售额换算 ---
    for rate in vat_rates:
        for tax_inclusive in [113, 226, 339, 565, 1130, 2260, 5650, 11300]:
            revenue = round(tax_inclusive / (1 + rate / 100), 2)
            tax = round(tax_inclusive - revenue, 2)
            content = f"某企业取得含税销售额{tax_inclusive}万元，适用税率{rate}%。不含税销售额为（　）万元。"
            wrong_opts = [
                round(tax_inclusive * (1 - rate / 100), 2),
                round(tax_inclusive / rate, 2),
                round(tax_inclusive * rate / 100, 2),
            ]
            all_opts = [(str(revenue), True)]
            seen = {str(revenue)}
            for w in wrong_opts:
                w_str = str(w)
                if w_str not in seen:
                    all_opts.append((w_str, False))
                    seen.add(w_str)
                if len(all_opts) == 4:
                    break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(revenue + random.uniform(-revenue*0.1, revenue*0.1), 2)
                fake_str = str(fake)
                if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                    all_opts.append((fake_str, False))
                    seen.add(fake_str)
            labels_4 = ["A", "B", "C", "D"]
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, "A",
                          f"不含税销售额=含税销售额/(1+税率)={tax_inclusive}/(1+{rate}%)={revenue}万元。",
                          3, "mock", opts_data)
            count += 1

    # --- 3. 企业所得税计算 ---
    incomes = [500, 800, 1000, 1500, 2000, 3000, 5000, 10000]
    non_taxable = [0, 50, 100, 200]
    exempt = [0, 50, 100]
    deductions = [300, 400, 500, 600, 700, 800, 1000]
    for income in incomes:
        for non_tax in non_taxable[:3]:
            for exempt_inc in exempt[:2]:
                for deduct in deductions[:3]:
                    taxable_income = income - non_tax - exempt_inc - deduct
                    if taxable_income <= 0:
                        continue
                    tax = round(taxable_income * 0.25, 2)
                    content = f"某企业收入总额{income}万元，不征税收入{non_tax}万元，免税收入{exempt_inc}万元，各项扣除{deduct}万元。应纳税所得额为（　）万元。"
                    wrong_opts = [
                        income - deduct,
                        income - non_tax - deduct,
                        income - exempt_inc - deduct,
                    ]
                    all_opts = [(str(taxable_income), True)]
                    seen = {str(taxable_income)}
                    for w in wrong_opts:
                        w_str = str(w)
                        if w_str not in seen:
                            all_opts.append((w_str, False))
                            seen.add(w_str)
                        if len(all_opts) == 4:
                            break
                    _attempts = 0
                    while len(all_opts) < 4 and _attempts < 200:
                        _attempts += 1
                        fake = taxable_income + int(random.uniform(-100, 100))
                        fake_str = str(fake)
                        if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                            all_opts.append((fake_str, False))
                            seen.add(fake_str)
                    labels_4 = ["A", "B", "C", "D"]
                    opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                    _add_question(db, kps["TAX-04-01"], "single_choice", content, "A",
                                  f"应纳税所得额=收入总额-不征税收入-免税收入-各项扣除={income}-{non_tax}-{exempt_inc}-{deduct}={taxable_income}万元。",
                                  4, "mock", opts_data)
                    count += 1

    # --- 4. 增值税进项税抵扣判断 ---
    vat_input_judgments = [
        ("企业购进的货物用于集体福利，其进项税额不得抵扣。", True, "用于集体福利不得抵扣。"),
        ("企业购进的货物用于个人消费，其进项税额不得抵扣。", True, "用于个人消费不得抵扣。"),
        ("企业购进的货物用于免征增值税项目，其进项税额不得抵扣。", True, "用于免税项目不得抵扣。"),
        ("企业购进的货物用于生产销售，其进项税额可以抵扣。", True, "用于应税项目可以抵扣。"),
        ("企业购进的生产设备，其进项税额可以抵扣。", True, "固定资产进项税可抵扣。"),
        ("企业购进的餐饮服务，其进项税额不得抵扣。", True, "餐饮服务不得抵扣。"),
        ("企业购进的旅客运输服务，其进项税额可以抵扣。", True, "符合条件可抵扣。"),
        ("小规模纳税人不得抵扣进项税额。", True, "小规模纳税人简易计税。"),
        ("企业非正常损失的购进货物，其进项税额不得抵扣。", True, "非正常损失不得抵扣。"),
        ("企业购进货物取得增值税专用发票，可以抵扣进项税额。", True, "专票可抵扣。"),
    ]
    for content, is_correct, explanation in vat_input_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["TAX-02-03"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 5. 个人所得税税率适用 ---
    pit_questions = [
        ("综合所得适用的税率是", "超额累进税率", "7级超额累进", ["比例税率", "定额税率", "全额累进税率"]),
        ("利息、股息、红利所得适用的税率是", "20%比例税率", "比例税率", ["超额累进税率", "10%", "30%"]),
        ("财产租赁所得适用的税率是", "20%比例税率", "比例税率", ["超额累进税率", "10%", "30%"]),
        ("财产转让所得适用的税率是", "20%比例税率", "比例税率", ["超额累进税率", "10%", "30%"]),
        ("偶然所得适用的税率是", "20%比例税率", "比例税率", ["超额累进税率", "10%", "30%"]),
        ("居民个人综合所得的扣除费用标准为每年", "60000元", "每月5000元×12", ["48000元", "72000元", "96000元"]),
        ("劳务报酬所得每次收入不超过4000元的，减除费用", "800元", "定额扣除800元", ["400元", "1000元", "20%"]),
        ("劳务报酬所得每次收入超过4000元的，减除费用为收入的", "20%", "定率扣除20%", ["10%", "15%", "30%"]),
    ]
    for question, answer, reason, wrongs in pit_questions:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"根据个人所得税法，{question}（　）。"
        result = _gen_single_choice(content, "A", f"{reason}。", 3, opts)
        _add_question(db, kps["TAX-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 6. 增值税基本原理判断 ---
    vat_theory_judgments = [
        ("增值税是价外税。", True, "增值税是价外税，不影响利润。"),
        ("增值税具有链条式抵扣机制。", True, "逐环节征收、逐环节抵扣。"),
        ("小规模纳税人适用简易计税方法。", True, "征收率3%（部分5%）。"),
        ("一般纳税人适用一般计税方法。", True, "销项税额-进项税额。"),
        ("增值税的纳税义务发生时间一般为收讫销售款项或取得索取销售款项凭据的当天。", True, "纳税义务发生时间。"),
        ("增值税专用发票可以作为进项税额抵扣的凭证。", True, "专票是抵扣凭证。"),
        ("增值税普通发票不能作为进项税额抵扣的凭证。", True, "普票不能抵扣（部分特殊除外）。"),
        ("进口货物应当缴纳增值税。", True, "进口环节增值税。"),
    ]
    for content, is_correct, explanation in vat_theory_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["TAX-04-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


# ========== 扩展题目生成（第二批）==========

def gen_accounting_extra(db: Session, kps: dict[str, int]) -> int:
    """会计扩展题目。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 购入资产业务（科目 × 金额 × 支付方式）---
    assets = [
        ("原材料", "银行存款", "存货增加，资产减少"),
        ("库存商品", "银行存款", "存货增加，资产减少"),
        ("固定资产", "银行存款", "固定资产增加，资产减少"),
        ("无形资产", "银行存款", "无形资产增加，资产减少"),
    ]
    amounts = [5, 10, 20, 30, 50, 80, 100, 150, 200, 300, 500, 800, 1000, 2000, 5000]
    for acct, payment, rule in assets:
        for amt in amounts:
            content = f"企业购入{acct}，价款{amt}万元，款项已用银行存款支付。正确的会计处理是（　）。"
            correct = f"借：{acct} {amt}万元；贷：{payment} {amt}万元"
            wrongs = [
                f"借：{payment} {amt}万元；贷：{acct} {amt}万元",
                f"借：{acct} {amt}万元；贷：应付账款 {amt}万元",
                f"借：库存商品 {amt}万元；贷：{payment} {amt}万元" if acct != "库存商品" else f"借：原材料 {amt}万元；贷：{payment} {amt}万元",
            ]
            opts = list(zip(labels, [correct] + wrongs))
            result = _gen_single_choice(content, "A", f"{rule}。借记{acct}，贷记{payment}。", 2, opts)
            _add_question(db, kps["ACC-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    # --- 销售业务（金额 × 税率）---
    revenues = [10, 20, 50, 100, 200, 300, 500, 800, 1000, 2000, 3000, 5000, 8000, 10000]
    rates = [13, 9, 6]
    for rev in revenues:
        for rate in rates:
            tax = round(rev * rate / 100, 2)
            total_rec = round(rev + tax, 2)
            content = f"企业销售商品，不含税售价{rev}万元，增值税税率{rate}%，款项已收存银行。正确的会计处理是（　）。"
            correct = f"借：银行存款 {total_rec}万元；贷：主营业务收入 {rev}万元，应交税费 {tax}万元"
            wrongs = [
                f"借：银行存款 {rev}万元；贷：主营业务收入 {rev}万元",
                f"借：应收账款 {total_rec}万元；贷：主营业务收入 {total_rec}万元",
                f"借：银行存款 {total_rec}万元；贷：主营业务收入 {total_rec}万元",
            ]
            opts = list(zip(labels, [correct] + wrongs))
            result = _gen_single_choice(content, "A", f"销售商品确认收入并收取含税款项。收入{rev}万元，销项税{tax}万元。", 3, opts)
            _add_question(db, kps["ACC-16-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    # --- 存货期末计量（成本 × 可变现净值）---
    costs = [50, 80, 100, 120, 150, 200, 250, 300, 400, 500]
    nv_rates = [0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2]
    for cost in costs:
        for nv_rate in nv_rates:
            nv = round(cost * nv_rate, 1)
            if nv < cost:
                provision = round(cost - nv, 1)
                content = f"某存货成本{cost}万元，可变现净值{nv}万元。应计提存货跌价准备（　）万元。"
                answer = str(provision)
                wrongs = [str(0), str(round(cost + nv, 1)), str(round(nv, 1))]
                opts_data = [("A", answer, True)] + [(labels[i+1], wrongs[i], False) for i in range(3)]
                _add_question(db, kps["ACC-03-02"], "single_choice", content, "A",
                              f"成本{cost}>可变现净值{nv}，计提跌价准备={cost}-{nv}={provision}万元。", 3, "mock", opts_data)
            else:
                content = f"某存货成本{cost}万元，可变现净值{nv}万元。应计提存货跌价准备（　）万元。"
                wrongs = [str(round(nv - cost, 1)), str(round(cost * 0.1, 1)), str(round(nv, 1))]
                opts_data = [("A", "0", True)] + [(labels[i+1], wrongs[i], False) for i in range(3)]
                _add_question(db, kps["ACC-03-02"], "single_choice", content, "A",
                              f"成本{cost}≤可变现净值{nv}，不计提跌价准备。", 3, "mock", opts_data)
            count += 1

    # --- 固定资产初始计量组合 ---
    prices = [50, 80, 100, 150, 200, 300, 500]
    transport_fees = [1, 2, 3, 5, 8, 10]
    install_fees = [2, 3, 5, 8, 10]
    for price in prices:
        for tf in transport_fees[:4]:
            for inst in install_fees[:3]:
                total = price + tf + inst
                content = f"企业购入需安装设备一台，买价{price}万元，运输费{tf}万元，安装费{inst}万元。该设备的入账价值为（　）万元。"
                wrongs = [str(price), str(price + tf), str(price + inst)]
                opts_data = [("A", str(total), True)] + [(labels[i+1], wrongs[i], False) for i in range(3)]
                _add_question(db, kps["ACC-04-01"], "single_choice", content, "A",
                              f"固定资产入账价值=买价+运输费+安装费={price}+{tf}+{inst}={total}万元。", 3, "mock", opts_data)
                count += 1

    return count


def gen_auditing_extra(db: Session, kps: dict[str, int]) -> int:
    """审计扩展题目。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 审计证据类型与可靠性 ---
    evidence_types = [
        ("外部书面证据", "高", "来自第三方的书面证据最可靠"),
        ("内部书面证据", "中", "企业内部生成的书面证据"),
        ("口头证据", "低", "口头陈述可靠性最低"),
        ("实物证据", "高", "实地观察或盘点获取的证据"),
        ("分析性证据", "中", "通过分析推理获取的证据"),
        ("环境证据", "中", "反映企业环境的证据"),
    ]
    for ev_type, reliability, reason in evidence_types:
        # 改为问类型
        wrong_types = [e[0] for e in evidence_types if e[0] != ev_type][:3]
        opts2 = list(zip(labels, [ev_type] + wrong_types))
        content = f"下列审计证据中，可靠性为「{reliability}」的是（　）。"
        result = _gen_single_choice(content, "A", f"{reason}。", 3, opts2)
        _add_question(db, kps["AUD-06-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 函证对象组合 ---
    confirmation_targets = [
        ("银行存款", "向银行函证", "银行存款必须函证"),
        ("应收账款", "向债务人函证", "应收账款向客户函证"),
        ("应付账款", "向债权人函证", "应付账款向供应商函证"),
        ("短期借款", "向银行函证", "向贷款银行函证"),
        ("长期借款", "向银行函证", "向贷款银行函证"),
        ("应收票据", "向出票人函证", "向票据出票人函证"),
        ("预收账款", "向购货方函证", "向预付款方函证"),
        ("预付账款", "向供货方函证", "向收款方函证"),
    ]
    all_targets = [t[0] for t in confirmation_targets]
    for target, method, reason in confirmation_targets:
        wrong_methods = [f"向{t}函证" if t != target else "自行盘点" for t in all_targets if t != target][:3]
        opts = list(zip(labels, [method] + wrong_methods))
        content = f"注册会计师审计{target}时，最适当的函证方式是（　）。"
        result = _gen_single_choice(content, "A", f"{reason}。", 3, opts)
        _add_question(db, kps["AUD-03-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 审计风险模型判断题 ---
    risk_judgments = [
        ("重大错报风险取决于被审计单位，注册会计师无法控制。", True, "重大错报风险是固有风险和控制风险的乘积。"),
        ("检查风险取决于审计程序的设计和执行。", True, "注册会计师可以控制检查风险。"),
        ("可接受的审计风险越低，需要的审计证据越多。", True, "风险越低，需要的保证程度越高。"),
        ("重大错报风险越高，可接受的检查风险越高。", False, "重大错报风险越高，可接受的检查风险越低。"),
        ("审计风险模型中，三个风险要素相互独立。", True, "各风险要素独立评估。"),
        ("审计风险是指财务报表存在重大错报而注册会计师发表不恰当意见的可能性。", True, "审计风险的定义。"),
        ("审计风险等于重大错报风险与检查风险之和。", False, "是乘积关系不是加法。"),
        ("在既定审计风险下，重大错报风险与检查风险呈反向关系。", True, "此消彼长。"),
        ("控制风险取决于内部控制的设计和运行。", True, "内部控制影响控制风险。"),
        ("固有风险不考虑内部控制的影响。", True, "固有风险在考虑内部控制之前评估。"),
    ]
    for content, is_correct, explanation in risk_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["AUD-06-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 内部控制应用题 ---
    ic_scenarios = [
        ("出纳人员不得兼任稽核、会计档案保管和收入、支出、费用、债权债务账目的登记工作", True, "不相容职务分离"),
        ("一项经济业务的全过程不能由一个人或一个部门单独完成", True, "职责分离原则"),
        ("授权批准与执行可以由同一人完成", False, "授权与执行应分离"),
        ("财产保管与记录保管可以由同一人完成", False, "保管与记录应分离"),
        ("业务执行与监督审核应分离", True, "执行与监督分离"),
        ("内部审计应独立于被审计部门", True, "审计独立性"),
        ("企业应建立定期轮岗制度", True, "轮岗有助于发现问题"),
        ("所有经济业务都需最高管理层审批", False, "应根据重要性分级授权"),
        ("信息系统管理员可以同时负责数据录入", False, "系统管理与数据录入应分离"),
        ("采购人员可以参与验收", False, "采购与验收应分离"),
    ]
    for content, is_correct, explanation in ic_scenarios:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["AUD-07-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 审计概念选择题 ---
    concept_choices = [
        ("审计的总体目标是对财务报表发表审计意见并出具审计报告", True, "审计总体目标"),
        ("审计范围受到限制可能导致无法表示意见", True, "审计范围限制"),
        ("合理保证是一个高水平但非绝对的保证", True, "合理保证定义"),
        ("审计准则要求注册会计师保持职业怀疑态度", True, "职业怀疑"),
        ("重要性水平越高，需要的审计证据越少", True, "重要性与证据反向关系"),
        ("重要性水平越低，需要的审计证据越多", True, "重要性与证据反向关系"),
        ("审计报告日期不应早于管理层签署财务报表的日期", True, "审计报告日期"),
        ("标准审计报告包含「按照审计准则执行」的表述", True, "标准审计报告"),
    ]
    for content, is_correct, explanation in concept_choices:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["AUD-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_strategy_extra(db: Session, kps: dict[str, int]) -> int:
    """战略与风险管理扩展题目。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 波特五力模型 ---
    five_forces = [
        ("现有竞争者的竞争程度", "行业内竞争"),
        ("潜在进入者的威胁", "新进入者"),
        ("替代品的威胁", "替代产品"),
        ("供应商的议价能力", "上游供应商"),
        ("购买者的议价能力", "下游客户"),
    ]
    force_scenarios = [
        ("行业内企业数量众多且实力相当", "现有竞争者的竞争程度", "竞争激烈"),
        ("行业进入壁垒低", "潜在进入者的威胁", "容易进入"),
        ("市场上出现功能相似的替代产品", "替代品的威胁", "替代品竞争"),
        ("原材料供应商集中度高", "供应商的议价能力", "供应商强势"),
        ("客户集中度高且采购量大", "购买者的议价能力", "客户强势"),
        ("行业增长率下降", "现有竞争者的竞争程度", "增长放缓竞争加剧"),
        ("行业需要巨额资本投入", "潜在进入者的威胁", "资本壁垒高"),
        ("产品差异化程度高", "潜在进入者的威胁", "差异化壁垒"),
        ("转换成本低的替代品出现", "替代品的威胁", "转换成本低"),
        ("原材料来源单一", "供应商的议价能力", "来源单一"),
        ("大客户占比超过50%", "购买者的议价能力", "客户集中"),
        ("行业产能过剩", "现有竞争者的竞争程度", "产能过剩"),
    ]
    for scenario, correct_force, reason in force_scenarios:
        wrong_forces = [f[0] for f in five_forces if f[0] != correct_force][:3]
        opts = list(zip(labels, [correct_force] + wrong_forces))
        content = f"在波特五力模型中，「{scenario}」主要影响（　）。"
        result = _gen_single_choice(content, "A", f"{reason}，影响{correct_force}。", 3, opts)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 价值链活动 ---
    value_chain = [
        ("内向后勤", "接收、存储和分配原材料"),
        ("生产经营", "将原材料转化为最终产品"),
        ("外向后勤", "收集、存储和分销产品"),
        ("市场营销", "提供购买途径并引导购买"),
        ("服务", "提供服务以保持产品价值"),
    ]
    support_activities = [
        ("采购", "购买用于企业价值链的各种投入"),
        ("技术开发", "改进产品和流程"),
        ("人力资源管理", "人员招聘、培训、薪酬"),
        ("企业基础设施", "总体管理、计划、财务、法律"),
    ]
    for activity, desc in value_chain:
        wrong_activities = [a[0] for a in value_chain if a[0] != activity][:2] + [support_activities[0][0]]
        opts = list(zip(labels, [activity] + wrong_activities))
        content = f"下列活动中，属于基本活动的是（　）。{desc}对应的活动是（　）。"
        result = _gen_single_choice(content, "A", f"{desc}属于基本活动中的{activity}。", 3, opts)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    for activity, desc in support_activities:
        wrong_activities = [a[0] for a in value_chain[:3]]
        opts = list(zip(labels, [activity] + wrong_activities))
        content = f"下列活动中，属于支持活动的是（　）。{desc}对应的活动是（　）。"
        result = _gen_single_choice(content, "A", f"{desc}属于支持活动中的{activity}。", 3, opts)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 风险应对策略 ---
    risk_responses = [
        ("风险规避", "退出或放弃导致风险的活动"),
        ("风险降低", "采取行动降低风险发生的可能性或影响"),
        ("风险转移", "通过保险、外包等方式将风险转移给第三方"),
        ("风险接受", "不采取任何行动，自行承担风险"),
    ]
    response_scenarios = [
        ("企业决定停止生产某亏损产品", "风险规避"),
        ("企业为固定资产购买保险", "风险转移"),
        ("企业加强内部控制减少错误发生", "风险降低"),
        ("企业认为某风险影响很小决定不处理", "风险接受"),
        ("企业将IT运维外包给专业公司", "风险转移"),
        ("企业通过多样化采购降低供应中断风险", "风险降低"),
        ("企业退出某个高风险市场", "风险规避"),
        ("企业设立风险准备金应对潜在损失", "风险接受"),
    ]
    for scenario, correct_response in response_scenarios:
        wrong_responses = [r[0] for r in risk_responses if r[0] != correct_response][:3]
        opts = list(zip(labels, [correct_response] + wrong_responses))
        content = f"{scenario}，这属于风险应对策略中的（　）。"
        result = _gen_single_choice(content, "A", f"{scenario}属于{correct_response}。", 3, opts)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 战略选择判断题 ---
    strategy_judgments = [
        ("密集型战略包括市场渗透、市场开发和产品开发。", True, "密集型战略的三种类型。"),
        ("后向一体化是指企业向其上游供应商方向扩展。", True, "向供应链上游扩展。"),
        ("前向一体化是指企业向其下游分销商方向扩展。", True, "向供应链下游扩展。"),
        ("横向一体化是指企业收购同行业的竞争对手。", True, "同行业并购。"),
        ("相关多元化是指进入与现有业务相关的行业。", True, "业务关联。"),
        ("非相关多元化是指进入与现有业务无关的行业。", True, "业务不关联。"),
        ("一体化战略可以降低交易成本。", True, "减少市场交易。"),
        ("多元化战略可以分散风险。", True, "不把鸡蛋放在一个篮子里。"),
        ("市场开发战略是指向现有市场销售新产品。", False, "市场开发是向新市场销售现有产品。"),
        ("产品开发战略是指向现有市场销售新产品。", True, "产品开发定义。"),
    ]
    for content, is_correct, explanation in strategy_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- SWOT 判断题 ---
    swot_judgments = [
        ("SWOT分析中S和W是内部因素，O和T是外部因素。", True, "内部因素包括优势和劣势。"),
        ("SWOT分析中O和T是内部因素。", False, "O和T是外部因素。"),
        ("SO战略是利用内部优势抓住外部机会。", True, "增长型战略。"),
        ("WT战略是克服内部劣势规避外部威胁。", True, "防御型战略。"),
        ("ST战略是利用内部优势规避外部威胁。", True, "多元化战略。"),
        ("WO战略是利用外部机会克服内部劣势。", True, "扭转型战略。"),
        ("SWOT分析可以帮助企业制定战略。", True, "SWOT用于战略制定。"),
        ("SWOT分析中的优势是指企业相对于竞争对手的长处。", True, "优势是相对的。"),
    ]
    for content, is_correct, explanation in swot_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["STR-02-03"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_law_extra(db: Session, kps: dict[str, int]) -> int:
    """经济法扩展题目。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 公司法数字题（扩展）---
    extra_numbers = [
        ("有限责任公司的董事会成员为", "3-13人", ["1-5人", "5-9人", "5-19人"]),
        ("股份有限公司的董事会成员为", "5-19人", ["3-13人", "3-9人", "7-15人"]),
        ("监事会的职工代表比例不得低于", "1/3", ["1/2", "1/4", "1/5"]),
        ("公司减少注册资本后的最低限额，有限责任公司为", "3万元", ["1万元", "5万元", "10万元"]),
        ("公司减少注册资本后的最低限额，股份有限公司为", "500万元", ["100万元", "300万元", "1000万元"]),
        ("股东会临时会议应由代表多少以上表决权的股东提议", "1/10", ["1/3", "1/2", "1/4"]),
        ("董事会临时会议应由多少以上董事提议", "1/3", ["1/10", "1/2", "1/4"]),
        ("公司法定公积金转增资本后留存的部分不得少于转增前注册资本的", "25%", ["10%", "50%", "30%"]),
        ("公司提取法定公积金的比例为税后利润的", "10%", ["5%", "15%", "20%"]),
        ("法定公积金累计达到注册资本的多少以上可以不再提取", "50%", ["30%", "25%", "100%"]),
        ("公司分配当年税后利润前应先弥补亏损和", "提取法定公积金", ["缴纳税款", "支付股利", "计提坏账准备"]),
        ("发起人持有的本公司股份自公司成立之日起多少年内不得转让", "1年", ["2年", "3年", "5年"]),
        ("公司公开发行股份前已发行的股份自上市交易之日起多少日内不得转让", "1年", ["6个月", "2年", "3年"]),
        ("董事、监事、高级管理人员在任职期间每年转让的股份不得超过其所持股份的", "25%", ["10%", "50%", "100%"]),
        ("股东大会作出修改公司章程的决议需经多少以上表决权通过", "2/3", ["1/2", "3/4", "1/3"]),
    ]
    for question, answer, wrongs in extra_numbers:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"根据《公司法》，{question}（　）。"
        result = _gen_single_choice(content, "A", f"《公司法》相关规定。", 3, opts)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 公司治理选择题（扩展）---
    gov_choices = [
        ("下列属于股东会职权的是", "决定公司的经营方针和投资计划", ["决定公司内部管理机构设置", "检查公司财务", "制定具体规章制度"]),
        ("下列属于董事会职权的是", "决定公司的经营计划和投资方案", ["选举和更换董事", "检查公司财务", "制定公司章程"]),
        ("下列属于监事会职权的是", "检查公司财务", ["决定经营方针", "聘任经理", "决定投资计划"]),
        ("下列属于经理职权的是", "组织实施公司年度经营计划", ["决定经营方针", "召集股东会", "检查公司财务"]),
        ("股东会的表决权按", "出资比例", ["股东人数", "董事人数", "职位高低"]),
        ("股份有限公司股东大会的表决权按", "股份比例", ["股东人数", "职位高低", "出资额"]),
        ("公司合并决议需经多少表决权通过", "2/3以上", ["过半数", "1/3以上", "全体一致"]),
        ("公司分立决议需经多少表决权通过", "2/3以上", ["过半数", "1/3以上", "全体一致"]),
        ("公司解散决议需经多少表决权通过", "2/3以上", ["过半数", "1/3以上", "全体一致"]),
        ("增减注册资本决议需经多少表决权通过", "2/3以上", ["过半数", "1/3以上", "全体一致"]),
    ]
    for question, answer, wrongs in gov_choices:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"公司法相关规定。", 3, opts)
        _add_question(db, kps["LAW-05-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 合同法选择题（扩展）---
    contract_choices = [
        ("要约的撤回通知应当在要约到达受要约人之前或", "与要约同时到达", ["要约到达后到达", "承诺发出前到达", "任何时候都可以"]),
        ("要约的撤销通知应当在受要约人发出承诺通知之前", "到达受要约人", ["到达要约人", "发出", "承诺到达后"]),
        ("下列属于要约失效情形的是", "受要约人拒绝要约的通知到达要约人", ["要约到达受要约人", "要约发出后", "承诺发出前"]),
        ("下列属于要约失效情形的是", "要约人依法撤销要约", ["要约到达受要约人", "受要约人发出承诺", "合同成立后"]),
        ("下列属于要约失效情形的是", "承诺期限届满受要约人未作出承诺", ["要约到达受要约人", "受要约人发出承诺", "要约人发出要约"]),
        ("下列属于要约失效情形的是", "受要约人对要约的内容作出实质性变更", ["要约到达受要约人", "受要约人收到要约", "要约人发出要约"]),
        ("合同成立的标志是", "承诺生效", ["要约到达", "合同签字", "合同公证"]),
        ("合同生效的条件不包括", "必须经过公证", ["当事人具有相应民事行为能力", "意思表示真实", "不违反法律强制性规定"]),
        ("下列合同中属于无效合同的是", "违反法律强制性规定的合同", ["因重大误解订立的合同", "显失公平的合同", "以欺诈手段订立的合同"]),
        ("下列合同中属于可撤销合同的是", "因重大误解订立的合同", ["违反法律强制性规定的合同", "损害社会公共利益的合同", "恶意串通损害他人利益的合同"]),
        ("撤销权的行使期限为自知道或应当知道撤销事由之日起", "1年", ["6个月", "2年", "5年"]),
        ("合同终止的原因不包括", "合同公证完成", ["债务已经按照约定履行", "合同解除", "债务相互抵销"]),
    ]
    for question, answer, wrongs in contract_choices:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"根据《合同法》，{question}（　）。"
        result = _gen_single_choice(content, "A", f"合同法相关规定。", 3, opts)
        _add_question(db, kps["LAW-03-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 合同履行判断题（扩展）---
    performance_judgments = [
        ("当事人应当按照约定全面履行自己的义务。", True, "全面履行原则。"),
        ("当事人应当遵循诚实信用原则履行义务。", True, "诚信原则。"),
        ("合同生效后当事人不得因姓名、名称的变更而不履行合同义务。", True, "合同相对性。"),
        ("同时履行抗辩权要求双方义务没有先后履行顺序。", True, "同时履行条件。"),
        ("先履行抗辩权要求先履行一方未履行或履行不符合约定。", True, "先履行抗辩权条件。"),
        ("不安抗辩权要求先履行一方有确切证据证明对方经营状况恶化。", True, "不安抗辩权条件。"),
        ("行使不安抗辩权后，对方提供担保的应当恢复履行。", True, "不安抗辩权的恢复。"),
        ("违约金具有补偿性和惩罚性双重属性。", True, "违约金性质。"),
        ("当事人既约定违约金又约定定金的，可以同时适用。", False, "只能选择适用其一。"),
        ("定金合同从实际交付定金之日起生效。", True, "定金实践性合同。"),
        ("给付定金的一方不履行债务的，无权要求返还定金。", True, "定金罚则。"),
        ("收受定金的一方不履行债务的，应当双倍返还定金。", True, "定金罚则。"),
    ]
    for content, is_correct, explanation in performance_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["LAW-03-02"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_tax_extra(db: Session, kps: dict[str, int]) -> int:
    """税法扩展题目。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 增值税应纳税额计算（销项-进项）---
    output_rates = [13, 9, 6]
    output_amounts = [100, 200, 500, 1000, 2000, 5000, 10000]
    input_amounts = [30, 50, 80, 100, 200, 500, 800, 1000, 2000]
    input_rates = [13, 9]
    for out_rate in output_rates:
        for out_amt in output_amounts:
            output_tax = round(out_amt * out_rate / 100, 2)
            for in_amt in input_amounts[:5]:
                for in_rate in input_rates:
                    input_tax = round(in_amt * in_rate / 100, 2)
                    payable = round(output_tax - input_tax, 2)
                    if payable <= 0:
                        payable_val = 0
                    else:
                        payable_val = payable
                    content = f"某企业当月不含税销售额{out_amt}万元（税率{out_rate}%），购进原材料不含税{in_amt}万元（税率{in_rate}%）。应纳增值税为（　）万元。"
                    wrongs = [
                        str(round(output_tax + input_tax, 2)),
                        str(round(output_tax, 2)),
                        str(round(input_tax, 2)),
                    ]
                    all_opts = [(str(payable_val), True)]
                    seen = {str(payable_val)}
                    for w in wrongs:
                        if w not in seen:
                            all_opts.append((w, False))
                            seen.add(w)
                        if len(all_opts) == 4:
                            break
                    _attempts = 0
                    while len(all_opts) < 4 and _attempts < 200:
                        _attempts += 1
                        fake = round(payable_val + random.uniform(-payable_val*0.3, payable_val*0.3), 2)
                        fake_str = str(fake)
                        if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                            all_opts.append((fake_str, False))
                            seen.add(fake_str)
                    labels_4 = ["A", "B", "C", "D"]
                    opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                    _add_question(db, kps["TAX-02-02"], "single_choice", content, "A",
                                  f"应纳增值税=销项税额-进项税额={output_tax}-{input_tax}={payable_val}万元。",
                                  4, "mock", opts_data)
                    count += 1

    # --- 企业所得税税额计算 ---
    taxable_incomes = [50, 100, 200, 300, 500, 800, 1000, 2000, 3000, 5000, 10000, 20000]
    rates_tax = [0.25, 0.20, 0.15]
    rate_labels = {0.25: "25%", 0.20: "20%（小型微利企业）", 0.15: "15%（高新技术企业）"}
    for income in taxable_incomes:
        for rate in rates_tax:
            tax = round(income * rate, 2)
            content = f"某企业应纳税所得额{income}万元，适用税率{rate_labels[rate]}。应纳企业所得税为（　）万元。"
            wrongs = [
                str(round(income * (rate + 0.05), 2)),
                str(round(income * (rate - 0.05), 2)),
                str(round(income * 0.1, 2)),
            ]
            all_opts = [(str(tax), True)]
            seen = {str(tax)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False))
                    seen.add(w)
                if len(all_opts) == 4:
                    break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(tax + random.uniform(-tax*0.2, tax*0.2), 2)
                fake_str = str(fake)
                if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                    all_opts.append((fake_str, False))
                    seen.add(fake_str)
            labels_4 = ["A", "B", "C", "D"]
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["TAX-04-01"], "single_choice", content, "A",
                          f"应纳税额=应纳税所得额×税率={income}×{rate_labels[rate]}={tax}万元。",
                          3, "mock", opts_data)
            count += 1

    # --- 税法概念选择题 ---
    tax_concepts = [
        ("增值税的基本税率是", "13%", ["6%", "9%", "3%"]),
        ("增值税的低税率不包括", "17%", ["9%", "6%", "3%"]),
        ("小规模纳税人的征收率一般为", "3%", ["6%", "9%", "13%"]),
        ("企业所得税的基本税率是", "25%", ["15%", "20%", "30%"]),
        ("高新技术企业的企业所得税税率是", "15%", ["10%", "20%", "25%"]),
        ("小型微利企业的企业所得税税率是", "20%", ["15%", "25%", "30%"]),
        ("个人所得税综合所得的最高边际税率是", "45%", ["30%", "35%", "40%"]),
        ("个人所得税综合所得的最低税率是", "3%", ["5%", "10%", "20%"]),
        ("个人所得税综合所得的减除费用标准为每月", "5000元", ["3000元", "3500元", "8000元"]),
        ("个人所得税综合所得的减除费用标准为每年", "60000元", ["36000元", "42000元", "96000元"]),
        ("下列项目中免征增值税的是", "农业生产者销售的自产农产品", ["销售货物", "提供加工劳务", "进口货物"]),
        ("下列项目中免征企业所得税的是", "国债利息收入", ["股息收入", "租金收入", "销售收入"]),
    ]
    for question, answer, wrongs in tax_concepts:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"税法相关规定。", 2, opts)
        _add_question(db, kps["TAX-04-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 个人所得税计算 ---
    monthly_incomes = [8000, 10000, 15000, 20000, 30000, 50000, 80000, 100000]
    for income in monthly_incomes:
        taxable = income - 5000
        if taxable <= 0:
            continue
        # 简化计算：3%至45%超额累进
        if taxable <= 3000:
            tax = round(taxable * 0.03, 2)
        elif taxable <= 12000:
            tax = round(3000 * 0.03 + (taxable - 3000) * 0.10, 2)
        elif taxable <= 25000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + (taxable - 12000) * 0.20, 2)
        elif taxable <= 35000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + (taxable - 25000) * 0.25, 2)
        elif taxable <= 55000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + 10000 * 0.25 + (taxable - 35000) * 0.30, 2)
        elif taxable <= 80000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + 10000 * 0.25 + 20000 * 0.30 + (taxable - 55000) * 0.35, 2)
        else:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + 10000 * 0.25 + 20000 * 0.30 + 25000 * 0.35 + (taxable - 80000) * 0.45, 2)

        content = f"某居民个人当月取得工资薪金{income}元，减除费用5000元后，应纳个人所得税为（　）元。（不考虑专项扣除和专项附加扣除）"
        wrongs = [
            str(round(tax * 1.1, 2)),
            str(round(tax * 0.9, 2)),
            str(round(taxable * 0.20, 2)),
        ]
        all_opts = [(str(tax), True)]
        seen = {str(tax)}
        for w in wrongs:
            if w not in seen:
                all_opts.append((w, False))
                seen.add(w)
            if len(all_opts) == 4:
                break
        _attempts = 0
        while len(all_opts) < 4 and _attempts < 200:
            _attempts += 1
            fake = round(tax + random.uniform(-tax*0.2, tax*0.2), 2)
            fake_str = str(fake)
            if fake_str not in seen and (fake > 0 or len(all_opts) < 2):
                all_opts.append((fake_str, False))
                seen.add(fake_str)
        labels_4 = ["A", "B", "C", "D"]
        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
        _add_question(db, kps["TAX-05-01"], "single_choice", content, "A",
                      f"应纳税所得额={income}-5000={taxable}元，按超额累进税率计算，应纳税额={tax}元。",
                      4, "mock", opts_data)
        count += 1

    return count


# ========== 第三批：大规模扩展题目 ==========

def gen_accounting_batch3(db: Session, kps: dict[str, int]) -> int:
    """会计第三批：折旧方法、存货计价、坏账准备、财务报表。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # 确保需要的知识点存在
    kps["ACC-03-01"] = _ensure_kp(db, "ACC-03-01", "存货的初始计量", "会计", "第三章 存货", "存货入账价值及发出计价方法", 3)
    # ACC-05-01 now exists in seed_data as 无形资产
    db.flush()

    # --- 1. 双倍余额递减法折旧 ---
    origins = [100, 200, 300, 500, 800, 1000, 1500, 2000, 3000, 5000]
    years_list = [5, 8, 10]
    for origin in origins:
        for years in years_list:
            rate = 2 / years
            year1_dep = round(origin * rate, 2)
            book_y1 = round(origin - year1_dep, 2)
            year2_dep = round(book_y1 * rate, 2)
            content = f"某固定资产原值{origin}万元，预计使用{years}年，采用双倍余额递减法计提折旧。第一年折旧额为（　）万元。"
            wrongs = [str(round(origin / years, 2)), str(round(year2_dep, 2)), str(round(origin * 0.1, 2))]
            all_opts = [(str(year1_dep), True)]
            seen = {str(year1_dep)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(year1_dep + random.uniform(-year1_dep*0.3, year1_dep*0.3), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["ACC-04-02"], "single_choice", content, "A",
                          f"双倍余额递减法第一年折旧=原值×(2/年限)={origin}×(2/{years})={year1_dep}万元。", 4, "mock", opts_data)
            count += 1

            # 第二年折旧
            content2 = f"某固定资产原值{origin}万元，预计使用{years}年，采用双倍余额递减法计提折旧。第二年折旧额为（　）万元。"
            wrongs2 = [str(round(year1_dep, 2)), str(round(origin / years, 2)), str(round(book_y1 / years, 2))]
            all_opts2 = [(str(year2_dep), True)]
            seen2 = {str(year2_dep)}
            for w in wrongs2:
                if w not in seen2:
                    all_opts2.append((w, False)); seen2.add(w)
                if len(all_opts2) == 4: break
            _attempts = 0
            while len(all_opts2) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(year2_dep + random.uniform(-year2_dep*0.3, year2_dep*0.3), 2)
                fs = str(fake)
                if fs not in seen2 and fake > 0:
                    all_opts2.append((fs, False)); seen2.add(fs)
            opts_data2 = [(labels_4[i], all_opts2[i][0], all_opts2[i][1]) for i in range(min(4, len(all_opts2)))]
            _add_question(db, kps["ACC-04-02"], "single_choice", content2, "A",
                          f"第二年折旧=(原值-第一年折旧)×(2/年限)=({origin}-{year1_dep})×(2/{years})={year2_dep}万元。", 4, "mock", opts_data2)
            count += 1

    # --- 2. 年数总和法折旧 ---
    for origin in [200, 500, 1000, 2000, 3000]:
        for years in [5, 8, 10]:
            sum_years = years * (years + 1) / 2
            residual = round(origin * 0.05, 2)
            depreciable = origin - residual
            year1_dep = round(depreciable * years / sum_years, 2)
            year2_dep = round(depreciable * (years - 1) / sum_years, 2)
            content = f"某固定资产原值{origin}万元，预计净残值{residual}万元，预计使用{years}年，采用年数总和法。第一年折旧额为（　）万元。"
            wrongs = [str(round(depreciable / years, 2)), str(round(origin * 2 / years, 2)), str(round(year2_dep, 2))]
            all_opts = [(str(year1_dep), True)]
            seen = {str(year1_dep)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(year1_dep + random.uniform(-year1_dep*0.3, year1_dep*0.3), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["ACC-04-02"], "single_choice", content, "A",
                          f"年数总和法第一年折旧=(原值-净残值)×尚可使用年限/年数总和=({origin}-{residual})×{years}/{int(sum_years)}={year1_dep}万元。", 4, "mock", opts_data)
            count += 1

    # --- 3. 存货加权平均法 ---
    for batches in [
        [(100, 10), (200, 15), (150, 12)],
        [(300, 20), (250, 18), (400, 22)],
        [(500, 30), (600, 25), (450, 28)],
        [(1000, 50), (800, 45), (1200, 55)],
        [(2000, 100), (1500, 90), (1800, 95)],
    ]:
        total_cost = sum(p * q for p, q in batches)
        total_qty = sum(q for _, q in batches)
        avg_cost = round(total_cost / total_qty, 2)
        content = f"某企业分批购入存货："
        for i, (p, q) in enumerate(batches):
            content += f"第{i+1}批{q}件单价{p}元；"
        content += f"采用加权平均法，存货单位成本为（　）元。"
        wrongs = [str(round(total_cost / total_qty + 0.5, 2)), str(round(batches[0][0], 2)), str(round(total_cost / (total_qty + 10), 2))]
        all_opts = [(str(avg_cost), True)]
        seen = {str(avg_cost)}
        for w in wrongs:
            if w not in seen:
                all_opts.append((w, False)); seen.add(w)
            if len(all_opts) == 4: break
        _attempts = 0
        while len(all_opts) < 4 and _attempts < 200:
            _attempts += 1
            fake = round(avg_cost + random.uniform(-avg_cost*0.1, avg_cost*0.1), 2)
            fs = str(fake)
            if fs not in seen and fake > 0:
                all_opts.append((fs, False)); seen.add(fs)
        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
        _add_question(db, kps["ACC-03-01"], "single_choice", content, "A",
                      f"加权平均单位成本=总成本/总数量={total_cost}/{total_qty}={avg_cost}元。", 3, "mock", opts_data)
        count += 1

    # --- 4. 坏账准备计提 ---
    balances = [100000, 200000, 500000, 1000000, 2000000, 5000000]
    rates = [0.01, 0.03, 0.05, 0.10]
    for balance in balances:
        for rate in rates:
            provision = round(balance * rate, 2)
            content = f"某企业应收账款余额{balance}元，按{int(rate*100)}%计提坏账准备。应计提坏账准备金额为（　）元。"
            wrongs = [str(round(balance * (rate + 0.02), 2)), str(round(balance * (rate - 0.01), 2)), str(round(balance * 0.01, 2))]
            all_opts = [(str(provision), True)]
            seen = {str(provision)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(provision + random.uniform(-provision*0.2, provision*0.2), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["ACC-05-01"], "single_choice", content, "A",
                          f"坏账准备=应收账款余额×计提比例={balance}×{int(rate*100)}%={provision}元。", 3, "mock", opts_data)
            count += 1

    # --- 5. 会计等式判断题 ---
    accounting_judgments = [
        ("资产=负债+所有者权益是会计基本等式，也是资产负债表的理论基础。", True, "资产负债表左右两侧总额必须相等。"),
        ("收入-费用=利润是利润表的理论基础。", True, "利润表反映一定期间的经营成果。"),
        ('借贷记账法的规则是"有借必有贷，借贷必相等"。', True, "每笔业务至少涉及一个借方和一个贷方账户。"),
        ("资产类账户增加记贷方，减少记借方。", False, "资产类账户增加记借方，减少记贷方。"),
        ("负债类账户增加记借方，减少记贷方。", False, "负债类账户增加记贷方，减少记借方。"),
        ("所有者权益类账户增加记贷方，减少记借方。", True, "所有者权益与负债同属权益，增加记贷方。"),
        ("收入类账户增加记贷方，费用类账户增加记借方。", True, "收入增加所有者权益记贷方，费用减少所有者权益记借方。"),
        ("试算平衡表平衡说明账簿记录完全正确。", False, "试算平衡只能发现借贷不等，不能发现所有错误。"),
        ("复式记账法是对每项经济业务都在两个或两个以上账户中登记的方法。", True, "复式记账能全面反映资金运动。"),
        ("权责发生制以款项的实际收付为标准确认收入和费用。", False, "权责发生制以权利和责任的发生为标准，收付实现制才以实际收付为标准。"),
        ("会计主体假设界定了会计核算的空间范围。", True, "会计主体不同于法律主体。"),
        ("持续经营假设要求企业按照既定的经营方针和目标持续经营下去。", True, "持续经营是会计核算的前提条件。"),
        ("会计分期假设将企业持续经营的活动划分为相等的期间。", True, "会计分期是定期报告的基础。"),
        ("货币计量假设要求以货币作为统一的计量单位。", True, "货币计量是会计的基本特征。"),
        ("历史成本原则要求资产按照当前市场价值计量。", False, "历史成本原则要求按取得时的实际成本计量。"),
        ("谨慎性原则要求不高估资产和收入，不低估负债和费用。", True, "谨慎性是会计信息质量要求之一。"),
        ("实质重于形式要求按经济实质而非法律形式进行会计处理。", True, "如售后回购不确认收入。"),
        ("固定资产折旧是固定资产价值在使用中逐渐转移的过程。", True, "折旧反映资产损耗。"),
        ("存货发出计价方法一经确定不得变更。", False, "会计准则允许在合理情况下变更计价方法。"),
        ("无形资产摊销方法应当反映其经济利益的预期消耗方式。", True, "摊销方法应与经济利益实现方式一致。"),
    ]
    for content, is_correct, explanation in accounting_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["ACC-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_finance_batch3(db: Session, kps: dict[str, int]) -> int:
    """财务管理第三批：WACC、NPV、比率分析、债券估值。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # 确保需要的知识点存在
    kps["FCM-03-01"] = _ensure_kp(db, "FCM-03-01", "资本成本", "财务成本管理", "第三章 资本成本", "WACC计算、债务与权益资本成本", 4)
    # FCM-02-01 (财务报表分析) now exists in seed_data
    db.flush()

    # --- 1. WACC 加权平均资本成本 ---
    equities = [500, 1000, 2000, 3000, 5000, 8000, 10000]
    debts = [300, 500, 1000, 2000, 3000, 5000]
    cost_equities = [0.10, 0.12, 0.15, 0.18]
    cost_debts = [0.04, 0.05, 0.06, 0.08]
    tax_rates = [0.25, 0.15]
    for eq in equities:
        for debt in debts:
            for ce in cost_equities:
                for cd in cost_debts:
                    for tr in tax_rates:
                        total = eq + debt
                        w_eq = eq / total
                        w_debt = debt / total
                        after_tax_cd = cd * (1 - tr)
                        wacc = round(w_eq * ce + w_debt * after_tax_cd, 4)
                        content = f"某公司权益资本{eq}万元（成本{ce*100:.0f}%），债务资本{debt}万元（税前成本{cd*100:.0f}%），所得税率{tr*100:.0f}%。加权平均资本成本(WACC)为（　）。"
                        wrongs = [str(round(wacc + 0.01, 4)), str(round(wacc - 0.01, 4)), str(round(ce * w_eq, 4))]
                        all_opts = [(str(wacc), True)]
                        seen = {str(wacc)}
                        for w in wrongs:
                            if w not in seen:
                                all_opts.append((w, False)); seen.add(w)
                            if len(all_opts) == 4: break
                        _attempts = 0
                        while len(all_opts) < 4 and _attempts < 200:
                            _attempts += 1
                            fake = round(wacc + random.uniform(-0.02, 0.02), 4)
                            fs = str(fake)
                            if fs not in seen and fake > 0:
                                all_opts.append((fs, False)); seen.add(fs)
                        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                        _add_question(db, kps["FCM-01-03"], "single_choice", content, "A",
                                      f"WACC=权益比重×权益成本+债务比重×税后债务成本={w_eq:.4f}×{ce}+{w_debt:.4f}×{after_tax_cd:.4f}={wacc}。", 5, "mock", opts_data)
                        count += 1
                        if count >= 1000:  # 限制数量避免过多
                            break
                    if count >= 600: break
                if count >= 600: break
            if count >= 600: break
        if count >= 600: break

    # --- 2. 流动比率与速动比率 ---
    current_assets = [100, 200, 500, 800, 1000, 2000, 3000, 5000]
    inventories = [50, 100, 200, 300, 500, 800, 1000]
    current_liabs = [50, 100, 200, 400, 500, 1000, 2000]
    for ca in current_assets:
        for inv in inventories:
            if inv >= ca:
                continue
            for cl in current_liabs:
                if cl == 0:
                    continue
                cr = round(ca / cl, 2)
                qr = round((ca - inv) / cl, 2)
                # 流动比率
                content = f"某企业流动资产{ca}万元，流动负债{cl}万元。流动比率为（　）。"
                wrongs = [str(round(cr + 0.5, 2)), str(round(cr - 0.3, 2)), str(round(ca / (cl + 100), 2))]
                all_opts = [(str(cr), True)]
                seen = {str(cr)}
                for w in wrongs:
                    if w not in seen:
                        all_opts.append((w, False)); seen.add(w)
                    if len(all_opts) == 4: break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(cr + random.uniform(-0.5, 0.5), 2)
                    fs = str(fake)
                    if fs not in seen and fake > 0:
                        all_opts.append((fs, False)); seen.add(fs)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["FCM-02-01"], "single_choice", content, "A",
                              f"流动比率=流动资产/流动负债={ca}/{cl}={cr}。", 3, "mock", opts_data)
                count += 1
                # 速动比率
                content2 = f"某企业流动资产{ca}万元，其中存货{inv}万元，流动负债{cl}万元。速动比率为（　）。"
                wrongs2 = [str(round(qr + 0.5, 2)), str(round(qr - 0.3, 2)), str(round(ca / cl, 2))]
                all_opts2 = [(str(qr), True)]
                seen2 = {str(qr)}
                for w in wrongs2:
                    if w not in seen2:
                        all_opts2.append((w, False)); seen2.add(w)
                    if len(all_opts2) == 4: break
                _attempts = 0
                while len(all_opts2) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(qr + random.uniform(-0.5, 0.5), 2)
                    fs = str(fake)
                    if fs not in seen2 and fake > 0:
                        all_opts2.append((fs, False)); seen2.add(fs)
                opts_data2 = [(labels_4[i], all_opts2[i][0], all_opts2[i][1]) for i in range(min(4, len(all_opts2)))]
                _add_question(db, kps["FCM-02-01"], "single_choice", content2, "A",
                              f"速动比率=(流动资产-存货)/流动负债=({ca}-{inv})/{cl}={qr}。", 4, "mock", opts_data2)
                count += 1
                if count >= 1500:
                    break
            if count >= 1500: break
        if count >= 1500: break

    # --- 3. 财务管理判断题 ---
    fin_judgments = [
        ("货币的时间价值是指货币经过一定时间的投资和再投资所增加的价值。", True, "时间价值是财务管理的基础概念。"),
        ("复利终值系数(F/P,i,n)与复利现值系数(P/F,i,n)互为倒数。", True, "终值和现值是反向计算。"),
        ("年金是指等额、定期的系列收支。", True, "年金有普通年金、预付年金等类型。"),
        ("内部收益率(IRR)是使项目净现值为零的折现率。", True, "IRR是项目本身的收益率。"),
        ("当NPV>0时，项目不可行。", False, "NPV>0表示项目可行。"),
        ("当IRR>资本成本时，项目可行。", True, "IRR大于资本成本意味着项目创造价值。"),
        ("β系数衡量的是系统性风险。", True, "β系数反映个股相对于市场的波动。"),
        ("资本资产定价模型(CAPM)用于计算无风险收益率。", False, "CAPM用于计算预期收益率：E(R)=Rf+β(Rm-Rf)。"),
        ("经营杠杆系数越大，经营风险越小。", False, "经营杠杆越大，经营风险越大。"),
        ("财务杠杆反映息税前利润变动对每股收益的影响。", True, "财务杠杆与债务使用相关。"),
        ("加权平均资本成本(WACC)是各种资本成本的加权平均。", True, "权重按市场价值确定。"),
        ("剩余收益=投资利润-资本成本×投资额。", True, "剩余收益考虑了资本成本。"),
        ("经济增加值(EVA)=税后净营业利润-资本成本。", True, "EVA衡量价值创造。"),
        ("营运资金=流动资产-流动负债。", True, "营运资金反映短期偿债能力。"),
        ("存货周转率=营业成本/平均存货。", True, "存货周转率反映存货管理效率。"),
    ]
    for content, is_correct, explanation in fin_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["FCM-01-03"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_all_subjects_judgments(db: Session, kps: dict[str, int]) -> int:
    """全科目判断题批量生成。"""
    count = 0

    # 审计判断题
    audit_judgments = [
        ("审计的目的是提高财务报表预期使用者对财务报表的信赖程度。", True, "审计提供合理保证。"),
        ("合理保证是一种高水平的保证，但不是绝对保证。", True, "审计风险无法降为零。"),
        ("审计风险=重大错报风险×检查风险。", True, "审计风险模型的基本公式。"),
        ("重要性水平越低，审计风险越高。", False, "重要性水平越低，需要收集的审计证据越多。"),
        ("审计证据的充分性是对证据数量的衡量。", True, "充分性受样本量影响。"),
        ("审计证据的适当性是对证据质量的衡量。", True, "适当性包括相关性和可靠性。"),
        ("函证是获取外部审计证据的可靠方法。", True, "外部证据比内部证据更可靠。"),
        ("审计抽样适用于所有审计程序。", False, "审计抽样不适用于询问、观察等程序。"),
        ("控制测试是为了确定内部控制运行的有效性。", True, "控制测试评估内控执行情况。"),
        ("实质性程序是为了发现认定层次的重大错报。", True, "实质性程序包括细节测试和实质性分析。"),
        ("审计报告应当由注册会计师签名并盖章。", True, "审计报告需要CPA签名。"),
        ("管理层声明书是审计证据的一种。", True, "但证明力较弱，不能替代其他审计程序。"),
        ("持续经营假设存在重大不确定性时，审计师应出具保留意见。", False, "可能出具带强调事项段的无保留意见或无法表示意见。"),
        ("审计独立性是审计的灵魂。", True, "独立性是审计的本质要求。"),
        ("关键审计事项是审计报告中必须包含的内容。", True, "适用于上市实体审计报告。"),
        ("审计重要性是针对财务报表整体而言的。", True, "也有特定类别交易或余额的重要性。"),
        ("审计证据的可靠性受其来源和性质的影响。", True, "外部独立来源的证据更可靠。"),
        ("审计抽样风险包括抽样风险和非抽样风险。", True, "抽样风险分为影响审计效果和效率两类。"),
        ("分析程序可用于风险评估和实质性程序。", True, "分析程序用途广泛。"),
        ("审计工作底稿应当保存至少10年。", True, "会计师事务所应当自审计报告日起保存10年。"),
    ]
    for content, is_correct, explanation in audit_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["AUD-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 战略判断题
    strategy_judgments = [
        ("SWOT分析中的S代表优势(Strengths)。", True, "SWOT是优势、劣势、机会、威胁的缩写。"),
        ("SWOT分析中的O代表机会(Opportunities)。", True, "机会属于外部环境因素。"),
        ("波特五力模型包括行业内现有竞争者的竞争程度。", True, "五力之一。"),
        ("波特五力模型包括替代品的替代威胁。", True, "替代品威胁影响行业利润。"),
        ("成本领先战略要求企业成为行业中成本最低的生产者。", True, "成本领先是基本竞争战略之一。"),
        ("差异化战略要求企业提供独特的产品或服务。", True, "差异化创造客户价值。"),
        ("集中化战略可以是集中成本领先或集中差异化。", True, "集中化战略针对特定细分市场。"),
        ("BCG矩阵中明星类产品具有高增长高市场份额特征。", True, "明星产品需要大量投资。"),
        ("BCG矩阵中现金牛类产品具有低增长高市场份额特征。", True, "现金牛产生稳定现金流。"),
        ("BCG矩阵中问题类产品具有高增长低市场份额特征。", True, "问题产品需要选择性投资。"),
        ("BCG矩阵中瘦狗类产品具有低增长低市场份额特征。", True, "瘦狗产品应考虑退出。"),
        ("企业核心能力是企业在长期运作中形成的、竞争对手难以模仿的能力。", True, "核心能力具有稀缺性和不可替代性。"),
        ("价值链分析包括基本活动和辅助活动。", True, "价值链是战略分析工具。"),
        ("PEST分析用于分析宏观环境。", True, "PEST包括政治、经济、社会、技术。"),
        ("战略实施是将战略转化为行动的过程。", True, "战略实施包括组织结构调整等。"),
        ("平衡计分卡从财务、客户、内部流程、学习与成长四个维度衡量绩效。", True, "平衡计分卡是综合绩效评价工具。"),
        ("多元化战略可以分为相关多元化和非相关多元化。", True, "多元化降低经营风险。"),
        ("一体化战略包括纵向一体化和横向一体化。", True, "纵向一体化又分前向和后向。"),
        ("并购战略的动因包括获得规模经济和协同效应。", True, "协同效应是并购的重要动因。"),
        ("企业战略目标是企业在一定时期内要达到的预期成果。", True, "战略目标应具有挑战性和可实现性。"),
    ]
    for content, is_correct, explanation in strategy_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 经济法判断题
    law_judgments = [
        ("合同是平等主体的自然人、法人、其他组织之间设立、变更、终止民事权利义务关系的协议。", True, "合同是民事法律行为。"),
        ("要约是希望和他人订立合同的意思表示。", True, "要约应当内容具体确定。"),
        ("承诺是受要约人同意要约的意思表示。", True, "承诺生效时合同成立。"),
        ("要约邀请是希望他人向自己发出要约的意思表示。", True, "如寄送价目表、拍卖公告等。"),
        ("限制民事行为能力人订立的合同经法定代理人追认后有效。", True, "追认使合同自始有效。"),
        ("合同当事人一方违约后，对方应当采取适当措施防止损失扩大。", True, "这是减损义务。"),
        ("违约金过分高于造成的损失的，当事人可以请求人民法院予以适当减少。", True, "违约金以补偿性为主。"),
        ("定金的数额不得超过主合同标的额的20%。", True, "超过部分不产生定金效力。"),
        ("公司是企业法人，有独立的法人财产，享有法人财产权。", True, "公司以其全部财产对债务承担责任。"),
        ("有限责任公司的股东以其认缴的出资额为限对公司承担责任。", True, "有限责任是公司的基本特征。"),
        ("股份有限公司的股东以其认购的股份为限对公司承担责任。", True, "股份有限责任。"),
        ("公司法定代表人依照公司章程的规定，可以由董事长、执行董事或经理担任。", True, "法定代表人制度。"),
        ("股东会会议作出修改公司章程的决议，必须经代表三分之二以上表决权的股东通过。", True, "特别决议事项。"),
        ("董事会的职权包括召集股东会会议、执行股东会决议。", True, "董事会是公司的执行机构。"),
        ("监事会应当包括股东代表和适当比例的公司职工代表。", True, "监事会保护各方利益。"),
        ("票据是出票人签发的、约定自己或委托他人无条件支付确定金额的有价证券。", True, "票据包括汇票、本票、支票。"),
        ("汇票是出票人签发的、委托付款人在见票时无条件支付确定金额的票据。", True, "汇票是委付证券。"),
        ("本票是出票人自己支付的票据。", True, "本票是自付证券。"),
        ("支票的付款人只能是银行。", True, "支票是支付证券。"),
        ("破产申请受理后，债务人的财产由管理人接管。", True, "管理人负责破产财产的管理和处分。"),
    ]
    for content, is_correct, explanation in law_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 税法判断题
    tax_judgments = [
        ("增值税是对商品生产流通环节的增值额征收的一种税。", True, "增值税是价外税。"),
        ("增值税小规模纳税人征收率一般为3%。", True, "小规模纳税人适用简易计税。"),
        ("增值税一般纳税人适用简易计税方法。", False, "一般纳税人适用一般计税方法，简易计税是特殊情况。"),
        ("销项税额=销售额×税率。", True, "销售额不含税。"),
        ("进项税额是纳税人购进货物支付或负担的增值税额。", True, "进项税额可以抵扣。"),
        ("应纳增值税=销项税额-进项税额。", True, "一般计税方法。"),
        ("企业所得税的基本税率为25%。", True, "居民企业适用25%基本税率。"),
        ("高新技术企业适用15%的企业所得税优惠税率。", True, "鼓励技术创新。"),
        ("小型微利企业减按20%的税率征收企业所得税。", True, "小型微利企业税收优惠。"),
        ("企业所得税按年计算、分月或分季预缴。", True, "年终汇算清缴。"),
        ("个人所得税综合所得包括工资薪金、劳务报酬、稿酬和特许权使用费。", True, "综合所得概念。"),
        ("个人所得税综合所得的减除费用为每年60000元。", True, "每月5000元。"),
        ("个人所得税经营所得适用5%-35%的超额累进税率。", True, "五级超额累进。"),
        ("利息、股息、红利所得适用20%的比例税率。", True, "分类所得税率。"),
        ("房产税的计税依据是房产原值。", False, "房产税计税依据为房产余值或租金收入。"),
        ("契税的纳税人是转移土地、房屋权属的承受方。", True, "契税由承受方缴纳。"),
        ("印花税是对经济活动和经济交往中书立、领受的凭证征收的一种税。", True, "印花税是凭证税。"),
        ("城市维护建设税的计税依据是纳税人实际缴纳的增值税和消费税。", True, "附加税性质。"),
        ("税收征收管理法规定纳税人必须按期申报纳税。", True, "纳税申报是纳税人义务。"),
        ("税务机关有权对纳税人进行税务检查。", True, "税务检查是税务机关的职权。"),
    ]
    for content, is_correct, explanation in tax_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["TAX-04-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_all_subjects_concepts(db: Session, kps: dict[str, int]) -> int:
    """全科目概念选择题批量生成。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # 会计概念题
    acc_concepts = [
        ("下列各项中，属于流动资产的是", "货币资金", ["固定资产", "无形资产", "长期股权投资"]),
        ("下列各项中，属于非流动负债的是", "长期借款", ["应付账款", "短期借款", "应付票据"]),
        ("下列各项中，属于所有者权益的是", "盈余公积", ["应付账款", "银行存款", "应收账款"]),
        ("借贷记账法下，资产的增加应记入", "借方", ["贷方", "收方", "付方"]),
        ("借贷记账法下，负债的增加应记入", "贷方", ["借方", "收方", "付方"]),
        ("借贷记账法下，收入的增加应记入", "贷方", ["借方", "收方", "付方"]),
        ("借贷记账法下，费用的增加应记入", "借方", ["贷方", "收方", "付方"]),
        ("下列会计科目中，属于资产类的是", "应收账款", ["应付账款", "实收资本", "主营业务收入"]),
        ("下列会计科目中，属于负债类的是", "预收账款", ["预付账款", "银行存款", "资本公积"]),
        ("下列会计科目中，属于所有者权益类的是", "资本公积", ["应收账款", "应付账款", "管理费用"]),
        ("下列会计科目中，属于损益类的是", "管理费用", ["银行存款", "长期借款", "实收资本"]),
        ("下列会计科目中，属于成本类的是", "制造费用", ["财务费用", "销售费用", "管理费用"]),
        ("资产负债表是反映企业在某一特定日期财务状况的报表。资产负债表属于", "时点报表", ["时期报表", "动态报表", "流量报表"]),
        ("利润表是反映企业在一定会计期间经营成果的报表。利润表属于", "时期报表", ["时点报表", "静态报表", "存量报表"]),
        ("现金流量表中，购买固定资产支付的现金属于", "投资活动现金流量", ["经营活动现金流量", "筹资活动现金流量", "不列入现金流量表"]),
        ("现金流量表中，偿还债务支付的现金属于", "筹资活动现金流量", ["经营活动现金流量", "投资活动现金流量", "不列入现金流量表"]),
        ("下列各项中，不影响营业利润的是", "营业外收入", ["营业收入", "营业成本", "管理费用"]),
        ("下列各项中，属于财务报表附注内容的是", "会计政策变更", ["资产负债表", "利润表", "现金流量表"]),
        ("存货的确认条件之一是与该存货有关的经济利益很可能流入企业，另一个条件是", "该存货的成本能够可靠计量", ["存货的市场价格已知", "存货已入库", "存货已付款"]),
        ("固定资产的折旧方法不包括", "先进先出法", ["年限平均法", "双倍余额递减法", "年数总和法"]),
    ]
    for question, answer, wrongs in acc_concepts:
        opts = list(zip(labels_4, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"会计基础知识。", 2, opts)
        _add_question(db, kps["ACC-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 审计概念题
    audit_concepts = [
        ("审计证据的充分性主要受下列哪项影响", "样本量", ["审计费用", "审计时间", "审计报告类型"]),
        ("审计证据的适当性包括相关性和", "可靠性", ["充分性", "及时性", "完整性"]),
        ("下列审计证据中，可靠性最高的是", "银行询证函回函", ["管理层声明", "内部生成的凭证", "口头证据"]),
        ("审计风险的组成要素不包括", "控制风险偏好", ["重大错报风险", "检查风险", "固有风险"]),
        ("下列属于审计抽样方法的是", "属性抽样", ["全查法", "详查法", "任意抽样"]),
        ("审计报告的类型不包括", "审计建议书", ["无保留意见", "保留意见", "否定意见"]),
        ("注册会计师的审计意见旨在提高财务报表的", "可信赖程度", ["美观性", "篇幅", "利润"]),
        ("审计准则要求注册会计师遵守", "独立性原则", ["企业利益优先", "利润最大化", "客户至上"]),
        ("内部控制的基本要素不包括", "市场营销策略", ["控制环境", "风险评估", "控制活动"]),
        ("下列属于内部控制缺陷的是", "未实现控制目标", ["控制设计完美", "控制运行有效", "无任何偏差"]),
        ("审计工作底稿的归档期限是", "审计报告日后60天内", ["审计报告日前", "审计报告日后10天", "审计报告日后1年"]),
        ("审计工作底稿的保存期限是", "至少10年", ["5年", "3年", "20年"]),
        ("下列属于控制测试程序的是", "重新执行", ["函证", "盘点", "询问"]),
        ("下列属于实质性程序的是", "函证", ["重新执行", "穿行测试", "观察"]),
        ("审计重要性水平的基准通常是", "营业收入或净利润", ["员工人数", "办公面积", "成立年限"]),
    ]
    for question, answer, wrongs in audit_concepts:
        opts = list(zip(labels_4, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"审计基础知识。", 2, opts)
        _add_question(db, kps["AUD-01-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 战略概念题
    strategy_concepts = [
        ("企业战略层次不包括", "个人战略", ["公司战略", "业务单位战略", "职能战略"]),
        ("下列属于公司层战略的是", "多元化战略", ["成本领先战略", "差异化战略", "集中化战略"]),
        ("下列属于业务单位战略的是", "差异化战略", ["并购战略", "多元化战略", "国际化战略"]),
        ("PEST分析中P代表", "政治环境", ["经济环境", "社会环境", "技术环境"]),
        ("PEST分析中E代表", "经济环境", ["政治环境", "社会环境", "技术环境"]),
        ("波特五力模型不包括", "政府干预", ["供应商议价能力", "买方议价能力", "潜在进入者威胁"]),
        ("BCG矩阵的维度是", "市场增长率和市场份额", ["利润和成本", "销售额和利润", "规模和增长率"]),
        ("平衡计分卡的维度不包括", "员工人数", ["财务", "客户", "内部流程"]),
        ("企业核心竞争力特征不包括", "普遍性", ["稀缺性", "不可模仿性", "不可替代性"]),
        ("价值链的基本活动不包括", "采购管理", ["内部物流", "生产运营", "外部物流"]),
        ("价值链的辅助活动不包括", "生产运营", ["采购管理", "技术开发", "人力资源管理"]),
        ("下列属于横向一体化战略的是", "并购同行业竞争对手", ["收购供应商", "开设新零售店", "进入新行业"]),
        ("下列属于前向一体化战略的是", "收购分销商", ["收购供应商", "并购竞争对手", "开发新产品"]),
        ("下列属于后向一体化战略的是", "收购供应商", ["收购分销商", "并购竞争对手", "开发新产品"]),
        ("战略实施的主要障碍不包括", "天气变化", ["资源不足", "组织结构不匹配", "文化冲突"]),
    ]
    for question, answer, wrongs in strategy_concepts:
        opts = list(zip(labels_4, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"战略管理基础知识。", 2, opts)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 经济法概念题
    law_concepts = [
        ("合同订立的一般程序包括要约和", "承诺", ["要约邀请", "反要约", "新要约"]),
        ("下列不属于合同生效要件的是", "合同经公证", ["当事人具有相应民事行为能力", "意思表示真实", "不违反法律强制性规定"]),
        ("合同无效的情形不包括", "合同未经备案", ["恶意串通损害他人利益", "以合法形式掩盖非法目的", "损害社会公共利益"]),
        ("可撤销合同的事由不包括", "合同金额过大", ["重大误解", "显失公平", "欺诈胁迫"]),
        ("下列属于合同履行原则的是", "全面履行原则", ["利益最大化原则", "效率优先原则", "自由选择原则"]),
        ("合同的抗辩权不包括", "拒绝履行权", ["同时履行抗辩权", "先履行抗辩权", "不安抗辩权"]),
        ("违约责任的承担方式不包括", "行政处罚", ["继续履行", "采取补救措施", "赔偿损失"]),
        ("下列关于定金的说法正确的是", "定金具有担保性质", ["定金可以超过合同标的额30%", "定金不具有惩罚性", "收受定金方违约应双倍返还"]),
        ("公司设立的条件不包括", "有良好的商业信誉", ["有符合规定的股东", "有符合规定的注册资本", "有公司住所"]),
        ("有限责任公司的股东人数上限为", "50人", ["30人", "100人", "200人"]),
        ("股份有限公司的发起人人数为", "2人以上200人以下", ["1人以上", "5人以上", "10人以上"]),
        ("公司减资决议应当由", "股东会作出", ["董事会作出", "经理决定", "监事会作出"]),
        ("票据的特征不包括", "有因性", ["无因性", "要式性", "文义性"]),
        ("下列关于支票的说法正确的是", "支票的付款人为银行", ["支票可以远期", "支票可以用于异地结算", "支票没有金额限制"]),
        ("破产程序中，负责管理破产财产的是", "管理人", ["债务人", "债权人会议", "人民法院"]),
    ]
    for question, answer, wrongs in law_concepts:
        opts = list(zip(labels_4, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"经济法基础知识。", 2, opts)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # 税法概念题
    tax_concepts = [
        ("增值税的基本税率是", "13%", ["6%", "9%", "3%"]),
        ("增值税的低税率是", "9%", ["13%", "6%", "3%"]),
        ("小规模纳税人的标准是年应税销售额不超过", "500万元", ["100万元", "200万元", "1000万元"]),
        ("增值税的计税方法不包括", "累进计税法", ["一般计税方法", "简易计税方法", "扣缴计税法"]),
        ("下列项目适用9%增值税税率的是", "交通运输服务", ["金融服务", "现代服务", "销售货物"]),
        ("下列项目适用6%增值税税率的是", "金融服务", ["销售货物", "交通运输服务", "建筑服务"]),
        ("不得抵扣的进项税额不包括", "购进生产用原材料", ["用于简易计税项目", "用于集体福利", "用于个人消费"]),
        ("企业所得税的纳税义务人不包括", "个人独资企业", ["居民企业", "非居民企业", "股份有限公司"]),
        ("企业所得税的应纳税所得额计算公式为", "收入总额-不征税收入-免税收入-各项扣除-允许弥补的亏损", ["收入总额-成本", "收入总额-费用", "利润总额"]),
        ("下列支出可以在企业所得税前全额扣除的是", "合理的工资薪金支出", ["赞助支出", "行政罚款", "税收滞纳金"]),
        ("下列收入属于企业所得税免税收入的是", "国债利息收入", ["股息收入", "租金收入", "销售收入"]),
        ("个人所得税综合所得的税率结构是", "7级超额累进税率", ["5级超额累进税率", "比例税率", "定额税率"]),
        ("个人所得税综合所得最高边际税率是", "45%", ["35%", "40%", "30%"]),
        ("下列不属于个人所得税专项附加扣除的是", "商业保险费", ["子女教育", "住房贷款利息", "赡养老人"]),
        ("房产税的税率形式是", "比例税率", ["超额累进税率", "定额税率", "全额累进税率"]),
    ]
    for question, answer, wrongs in tax_concepts:
        opts = list(zip(labels_4, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"税法基础知识。", 2, opts)
        _add_question(db, kps["TAX-04-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_tax_batch3(db: Session, kps: dict[str, int]) -> int:
    """税法第三批：更多计算题组合。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # --- 1. 增值税销项税额（更多组合） ---
    rates = [13, 9, 6]
    amounts = [30, 50, 80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000]
    for rate in rates:
        for amt in amounts:
            tax = round(amt * rate / 100, 2)
            content = f"某企业销售货物不含税金额{amt}万元，增值税税率{rate}%。该笔业务的销项税额为（　）万元。"
            wrongs = [str(round(amt * (rate + 1) / 100, 2)), str(round(amt * (rate - 2) / 100, 2)),
                      str(round(amt * rate / 110, 2))]
            all_opts = [(str(tax), True)]
            seen = {str(tax)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(tax + random.uniform(-tax * 0.2, tax * 0.2), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, "A",
                          f"销项税额=不含税销售额×税率={amt}×{rate}%={tax}万元。", 3, "mock", opts_data)
            count += 1

    # --- 2. 含税销售额换算 ---
    for rate in rates:
        for amt in [113, 226, 339, 565, 1090, 1130, 2180, 3270, 5450, 10900]:
            tax = round(amt / (1 + rate / 100) * rate / 100, 2)
            content = f"某企业销售货物含税金额{amt}万元，增值税税率{rate}%。该笔业务的不含税销售额为（　）万元。"
            answer = round(amt / (1 + rate / 100), 2)
            wrongs = [str(round(amt * rate / 100, 2)), str(round(amt / (1 + rate / 100) + 5, 2)),
                      str(round(amt, 2))]
            all_opts = [(str(answer), True)]
            seen = {str(answer)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(answer + random.uniform(-answer * 0.1, answer * 0.1), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, "A",
                          f"不含税销售额=含税销售额÷(1+税率)={amt}÷(1+{rate}%)={answer}万元。", 3, "mock", opts_data)
            count += 1

    # --- 3. 企业所得税应纳税额（更多组合） ---
    incomes = [20, 30, 50, 60, 80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000, 20000, 25000]
    rates_cit = [(0.25, "25%"), (0.20, "20%"), (0.15, "15%"), (0.10, "10%（非居民企业）")]
    for income in incomes:
        for rate_val, rate_label in rates_cit:
            tax = round(income * rate_val, 2)
            content = f"某企业应纳税所得额{income}万元，适用企业所得税税率{rate_label}。应纳企业所得税为（　）万元。"
            wrongs = [str(round(income * (rate_val + 0.05), 2)), str(round(income * (rate_val - 0.05), 2)),
                      str(round(income * 0.1, 2))]
            all_opts = [(str(tax), True)]
            seen = {str(tax)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(tax + random.uniform(-tax * 0.2, tax * 0.2), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["TAX-04-01"], "single_choice", content, "A",
                          f"应纳税额=应纳税所得额×税率={income}×{rate_label}={tax}万元。", 3, "mock", opts_data)
            count += 1

    # --- 4. 个人所得税更多组合 ---
    monthly_incomes = [6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 11000, 12000, 13000, 14000, 15000, 16000, 17000, 18000, 19000, 20000, 22000, 25000, 28000, 30000, 35000, 40000, 45000, 50000, 55000, 60000, 70000, 80000, 90000, 100000, 120000, 150000, 200000, 250000, 300000]
    for income in monthly_incomes:
        taxable = income - 5000
        if taxable <= 0:
            continue
        if taxable <= 3000:
            tax = round(taxable * 0.03, 2)
            level = "3%"
        elif taxable <= 12000:
            tax = round(3000 * 0.03 + (taxable - 3000) * 0.10, 2)
            level = "10%部分"
        elif taxable <= 25000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + (taxable - 12000) * 0.20, 2)
            level = "20%部分"
        elif taxable <= 35000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + (taxable - 25000) * 0.25, 2)
            level = "25%部分"
        elif taxable <= 55000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + 10000 * 0.25 + (taxable - 35000) * 0.30, 2)
            level = "30%部分"
        elif taxable <= 80000:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + 10000 * 0.25 + 20000 * 0.30 + (taxable - 55000) * 0.35, 2)
            level = "35%部分"
        else:
            tax = round(3000 * 0.03 + 9000 * 0.10 + 13000 * 0.20 + 10000 * 0.25 + 20000 * 0.30 + 25000 * 0.35 + (taxable - 80000) * 0.45, 2)
            level = "45%部分"
        content = f"某居民个人当月工资薪金{income}元，减除费用5000元，应纳税所得额{taxable}元。应纳个人所得税为（　）元。"
        wrongs = [str(round(tax * 1.1, 2)), str(round(tax * 0.9, 2)), str(round(taxable * 0.20, 2))]
        all_opts = [(str(tax), True)]
        seen = {str(tax)}
        for w in wrongs:
            if w not in seen:
                all_opts.append((w, False)); seen.add(w)
            if len(all_opts) == 4: break
        _attempts = 0
        while len(all_opts) < 4 and _attempts < 200:
            _attempts += 1
            fake = round(tax + random.uniform(-tax * 0.2, tax * 0.2), 2)
            fs = str(fake)
            if fs not in seen and fake > 0:
                all_opts.append((fs, False)); seen.add(fs)
        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
        _add_question(db, kps["TAX-05-01"], "single_choice", content, "A",
                      f"按七级超额累进税率计算（适用{level}），应纳税额={tax}元。", 4, "mock", opts_data)
        count += 1

    return count


# ========== 第四批：补充薄弱科目 ==========

def gen_auditing_batch4(db: Session, kps: dict[str, int]) -> int:
    """审计第四批：抽样、重要性、审计意见。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # --- 1. 审计抽样样本量计算 ---
    populations = [1000, 2000, 5000, 10000, 20000, 50000]
    tolerable_rates = [0.02, 0.05, 0.10]
    expected_rates = [0.00, 0.01, 0.02]
    for pop in populations:
        for tr in tolerable_rates:
            for er in expected_rates:
                if er >= tr:
                    continue
                # 简化样本量公式 n = (pop * Z^2 * p * (1-p)) / (E^2 * (pop-1) + Z^2 * p * (1-p))
                # 简化: n ≈ 1 / (tr - er)^2 (近似)
                import math
                n = max(25, int(math.ceil(1.0 / (tr - er) ** 2 * 0.5)))
                if n > pop:
                    n = pop
                content = f"审计师对总体{pop}个项目进行属性抽样，可容忍偏差率{tr*100:.0f}%，预期偏差率{er*100:.0f}%。最小样本量约为（　）个。"
                wrongs = [str(n * 2), str(max(10, n // 2)), str(n + 50)]
                all_opts = [(str(n), True)]
                seen = {str(n)}
                for w in wrongs:
                    if w not in seen:
                        all_opts.append((w, False)); seen.add(w)
                    if len(all_opts) == 4: break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = n + random.randint(-n // 3, n // 3)
                    fs = str(fake)
                    if fs not in seen and fake > 0:
                        all_opts.append((fs, False)); seen.add(fs)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["AUD-06-02"], "single_choice", content, "A",
                              f"属性抽样样本量受总体规模、可容忍偏差率和预期偏差率影响。计算得样本量约{n}个。", 5, "mock", opts_data)
                count += 1

    # --- 2. 重要性水平计算 ---
    benchmarks = [("营业收入", 0.01), ("营业收入", 0.005), ("净利润", 0.05), ("净利润", 0.10),
                  ("总资产", 0.01), ("总资产", 0.005), ("净资产", 0.01), ("净资产", 0.005)]
    amounts_list = [1000, 2000, 5000, 10000, 20000, 50000, 100000, 500000, 1000000]
    for bench_name, bench_rate in benchmarks:
        for amt in amounts_list:
            materiality = round(amt * bench_rate, 2)
            content = f"某企业{bench_name}{amt}万元，审计师按{bench_rate*100:.1f}%确定整体重要性水平。重要性水平为（　）万元。"
            wrongs = [str(round(amt * bench_rate * 2, 2)), str(round(amt * bench_rate * 0.5, 2)),
                      str(round(amt * 0.01, 2))]
            all_opts = [(str(materiality), True)]
            seen = {str(materiality)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(materiality + random.uniform(-materiality * 0.3, materiality * 0.3), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["AUD-06-02"], "single_choice", content, "A",
                          f"重要性水平=基准×比例={amt}×{bench_rate*100:.1f}%={materiality}万元。", 4, "mock", opts_data)
            count += 1

    # --- 3. 审计风险模型计算 ---
    inherent_risks = [0.50, 0.60, 0.70, 0.80, 0.90]
    control_risks = [0.30, 0.40, 0.50, 0.60, 0.70]
    audit_risks = [0.05, 0.10]
    for ir in inherent_risks:
        for cr in control_risks:
            for ar in audit_risks:
                dr = round(ar / (ir * cr), 4)
                if dr > 1:
                    continue
                content = f"审计师评估的重大错报风险为{ir*100:.0f}%（固有风险{ir*100:.0f}%×控制风险{cr*100:.0f}%），可接受审计风险为{ar*100:.0f}%。可接受的检查风险为（　）。"
                wrongs = [str(round(dr + 0.05, 4)), str(round(dr - 0.05, 4)), str(round(ar / ir, 4))]
                all_opts = [(str(dr), True)]
                seen = {str(dr)}
                for w in wrongs:
                    if w not in seen:
                        all_opts.append((w, False)); seen.add(w)
                    if len(all_opts) == 4: break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(dr + random.uniform(-0.05, 0.05), 4)
                    fs = str(fake)
                    if fs not in seen and fake > 0:
                        all_opts.append((fs, False)); seen.add(fs)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["AUD-06-02"], "single_choice", content, "A",
                              f"检查风险=审计风险/重大错报风险={ar}/({ir}×{cr})={dr}。", 5, "mock", opts_data)
                count += 1

    return count


def gen_strategy_batch4(db: Session, kps: dict[str, int]) -> int:
    """战略第四批：BCG矩阵、五力分析、情景分析。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # --- 1. BCG矩阵分类 ---
    growth_rates = [5, 8, 10, 15, 20, 25, 30]
    shares = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
    competitor_shares = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
    for growth in growth_rates:
        for share in shares:
            for comp_share in competitor_shares:
                if comp_share >= share:
                    continue
                rel_share = round(share / comp_share, 2)
                if growth > 10 and rel_share > 1:
                    category = "明星类"
                    strategy = "加大投资"
                elif growth <= 10 and rel_share > 1:
                    category = "现金牛类"
                    strategy = "收割利润"
                elif growth > 10 and rel_share <= 1:
                    category = "问题类"
                    strategy = "选择性投资"
                else:
                    category = "瘦狗类"
                    strategy = "退出或剥离"
                content = f"某产品的市场增长率为{growth}%，相对市场份额为{rel_share}。根据BCG矩阵，该产品属于（　）。"
                wrongs_data = [("明星类", category == "明星类"), ("现金牛类", category == "现金牛类"),
                               ("问题类", category == "问题类"), ("瘦狗类", category == "瘦狗类")]
                wrongs_list = [c for c, _ in wrongs_data if c != category][:3]
                opts = list(zip(labels_4, [category] + wrongs_list))
                result = _gen_single_choice(content, "A", f"市场增长率{growth}%{'>10%' if growth > 10 else '≤10%'}且相对份额{rel_share}{'>1' if rel_share > 1 else '≤1'}，属于{category}，策略为{strategy}。", 3, opts)
                _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
                count += 1

    # --- 2. 五力分析判断 ---
    five_forces_scenarios = [
        ("行业内竞争加剧", "行业内现有竞争者的竞争", "竞争者数量增加或产品同质化"),
        ("新企业进入市场", "潜在进入者的威胁", "进入壁垒低时威胁大"),
        ("替代产品出现", "替代品的威胁", "替代品性价比高时威胁大"),
        ("供应商提高价格", "供应商的议价能力", "供应商集中度高时议价能力强"),
        ("客户要求降价", "购买者的议价能力", "客户集中度高时议价能力强"),
    ]
    for scenario, force, reason in five_forces_scenarios:
        for _ in range(20):
            content = f"{scenario}，这属于波特五力模型中的（　）。"
            wrongs = [f for f, _, _ in five_forces_scenarios if f != force][:3]
            opts = list(zip(labels_4, [force] + wrongs))
            result = _gen_single_choice(content, "A", f"{reason}。", 2, opts)
            _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
            count += 1

    return count


def gen_law_batch4(db: Session, kps: dict[str, int]) -> int:
    """经济法第四批：违约金、定金、公司资本。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # --- 1. 违约金计算 ---
    contract_amounts = [10000, 50000, 100000, 200000, 500000, 1000000, 2000000, 5000000]
    penalty_rates = [0.05, 0.10, 0.15, 0.20, 0.30]
    for amt in contract_amounts:
        for rate in penalty_rates:
            penalty = round(amt * rate, 2)
            content = f"某合同标的额{amt}元，约定违约金为标的额的{rate*100:.0f}%。违约方应支付的违约金为（　）元。"
            wrongs = [str(round(amt * (rate + 0.05), 2)), str(round(amt * (rate - 0.02), 2)),
                      str(round(amt * 0.1, 2))]
            all_opts = [(str(penalty), True)]
            seen = {str(penalty)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(penalty + random.uniform(-penalty * 0.2, penalty * 0.2), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["LAW-03-02"], "single_choice", content, "A",
                          f"违约金=合同标的额×违约金比例={amt}×{rate*100:.0f}%={penalty}元。", 3, "mock", opts_data)
            count += 1

    # --- 2. 定金计算 ---
    for amt in contract_amounts:
        for rate in [0.10, 0.15, 0.20]:
            deposit = round(amt * rate, 2)
            content = f"某合同标的额{amt}元，买方支付定金比例为{rate*100:.0f}%。定金金额为（　）元。"
            wrongs = [str(round(amt * (rate + 0.05), 2)), str(round(amt * 0.25, 2)),
                      str(round(amt * 0.05, 2))]
            all_opts = [(str(deposit), True)]
            seen = {str(deposit)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(deposit + random.uniform(-deposit * 0.2, deposit * 0.2), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["LAW-03-02"], "single_choice", content, "A",
                          f"定金=合同标的额×定金比例={amt}×{rate*100:.0f}%={deposit}元（不得超过20%）。", 3, "mock", opts_data)
            count += 1

            # 双倍返还定金
            double_return = round(deposit * 2, 2)
            content2 = f"某合同标的额{amt}元，买方已支付定金{deposit}元。卖方违约应双倍返还定金，返还金额为（　）元。"
            wrongs2 = [str(round(deposit * 3, 2)), str(round(deposit, 2)), str(round(amt * rate, 2))]
            all_opts2 = [(str(double_return), True)]
            seen2 = {str(double_return)}
            for w in wrongs2:
                if w not in seen2:
                    all_opts2.append((w, False)); seen2.add(w)
                if len(all_opts2) == 4: break
            _attempts = 0
            while len(all_opts2) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(double_return + random.uniform(-double_return * 0.2, double_return * 0.2), 2)
                fs = str(fake)
                if fs not in seen2 and fake > 0:
                    all_opts2.append((fs, False)); seen2.add(fs)
            opts_data2 = [(labels_4[i], all_opts2[i][0], all_opts2[i][1]) for i in range(min(4, len(all_opts2)))]
            _add_question(db, kps["LAW-03-02"], "single_choice", content2, "A",
                          f"收受定金方违约应双倍返还定金={deposit}×2={double_return}元。", 3, "mock", opts_data2)
            count += 1

    # --- 3. 公司注册资本与出资 ---
    capitals = [100, 500, 1000, 2000, 5000, 10000, 20000, 50000]
    shareholder_counts = [2, 3, 5, 10, 20, 50]
    for cap in capitals:
        for sc in shareholder_counts:
            per_capital = round(cap / sc, 2)
            content = f"某有限责任公司注册资本{cap}万元，共{sc}名股东均等出资。每名股东应出资（　）万元。"
            wrongs = [str(round(per_capital * 1.5, 2)), str(round(per_capital * 0.5, 2)),
                      str(round(cap / (sc + 5), 2))]
            all_opts = [(str(per_capital), True)]
            seen = {str(per_capital)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(per_capital + random.uniform(-per_capital * 0.2, per_capital * 0.2), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["LAW-05-01"], "single_choice", content, "A",
                          f"每名股东出资额=注册资本÷股东人数={cap}÷{sc}={per_capital}万元。", 2, "mock", opts_data)
            count += 1

    return count


def gen_accounting_batch4(db: Session, kps: dict[str, int]) -> int:
    """会计第四批：收入确认、利润计算、所有者权益。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # --- 1. 收入确认（五步法） ---
    amounts = [100, 200, 500, 800, 1000, 2000, 3000, 5000, 8000, 10000]
    tax_rates = [13, 9, 6]
    for amt in amounts:
        for tr in tax_rates:
            revenue = round(amt / (1 + tr / 100), 2)
            tax = round(amt - revenue, 2)
            content = f"某企业销售商品含税总额{amt}万元，增值税税率{tr}%。确认的营业收入为（　）万元。"
            wrongs = [str(round(amt * tr / 100, 2)), str(round(amt, 2)), str(round(amt / (1 + tr / 100) + 5, 2))]
            all_opts = [(str(revenue), True)]
            seen = {str(revenue)}
            for w in wrongs:
                if w not in seen:
                    all_opts.append((w, False)); seen.add(w)
                if len(all_opts) == 4: break
            _attempts = 0
            while len(all_opts) < 4 and _attempts < 200:
                _attempts += 1
                fake = round(revenue + random.uniform(-revenue * 0.1, revenue * 0.1), 2)
                fs = str(fake)
                if fs not in seen and fake > 0:
                    all_opts.append((fs, False)); seen.add(fs)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _add_question(db, kps["ACC-16-01"], "single_choice", content, "A",
                          f"营业收入=含税总额÷(1+税率)={amt}÷(1+{tr}%)={revenue}万元。", 3, "mock", opts_data)
            count += 1

    # --- 2. 利润计算 ---
    revenues_list = [80, 100, 150, 200, 300, 500, 800, 1000, 1500, 2000, 3000, 5000, 8000, 10000]
    cost_ratios = [0.50, 0.60, 0.70, 0.80]
    expense_ratios = [0.05, 0.10, 0.15]
    for rev in revenues_list:
        for cr in cost_ratios:
            for er in expense_ratios:
                cost = round(rev * cr, 2)
                expense = round(rev * er, 2)
                profit = round(rev - cost - expense, 2)
                content = f"某企业营业收入{rev}万元，营业成本占收入{cr*100:.0f}%，期间费用占收入{er*100:.0f}%。营业利润为（　）万元。"
                wrongs = [str(round(rev - cost, 2)), str(round(rev - expense, 2)), str(round(profit + rev * 0.1, 2))]
                all_opts = [(str(profit), True)]
                seen = {str(profit)}
                for w in wrongs:
                    if w not in seen:
                        all_opts.append((w, False)); seen.add(w)
                    if len(all_opts) == 4: break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(profit + random.uniform(-abs(profit) * 0.3 if profit != 0 else 5, abs(profit) * 0.3 if profit != 0 else 5), 2)
                    fs = str(fake)
                    if fs not in seen and (fake > 0 or len(all_opts) < 2):
                        all_opts.append((fs, False)); seen.add(fs)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["ACC-01-02"], "single_choice", content, "A",
                              f"营业利润=收入-成本-费用={rev}-{cost}-{expense}={profit}万元。", 4, "mock", opts_data)
                count += 1

    # --- 3. 所有者权益计算 ---
    capitals_list = [300, 500, 800, 1000, 1500, 2000, 3000, 5000, 8000, 10000, 15000, 20000, 30000]
    retained_list = [50, 100, 200, 300, 500, 800, 1000, 1500, 2000, 3000, 5000]
    surplus_list = [30, 50, 80, 100, 150, 200, 300, 500, 800, 1000]
    for cap in capitals_list:
        for ret in retained_list:
            for sur in surplus_list:
                equity = cap + ret + sur
                content = f"某公司实收资本{cap}万元，未分配利润{ret}万元，盈余公积{sur}万元。所有者权益总额为（　）万元。"
                wrongs = [str(round(equity - sur, 2)), str(round(cap + ret, 2)), str(round(equity + 100, 2))]
                all_opts = [(str(equity), True)]
                seen = {str(equity)}
                for w in wrongs:
                    if w not in seen:
                        all_opts.append((w, False)); seen.add(w)
                    if len(all_opts) == 4: break
                _attempts = 0
                while len(all_opts) < 4 and _attempts < 200:
                    _attempts += 1
                    fake = round(equity + random.uniform(-equity * 0.05, equity * 0.05), 2)
                    fs = str(fake)
                    if fs not in seen and fake > 0:
                        all_opts.append((fs, False)); seen.add(fs)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _add_question(db, kps["ACC-01-02"], "single_choice", content, "A",
                              f"所有者权益=实收资本+未分配利润+盈余公积={cap}+{ret}+{sur}={equity}万元。", 3, "mock", opts_data)
                count += 1

    return count


# ========== 第五批：补充概念与判断题 ==========

def gen_concepts_batch5(db: Session, kps: dict[str, int]) -> int:
    """第五批概念选择题，覆盖各科目高频考点。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # 确保需要的知识点存在
    # STR-05-01 (风险与风险管理概述) now exists in seed_data
    # TAX-02-03 (增值税进项税额) now exists in seed_data
    db.flush()

    all_concepts = [
        # 会计
        ("ACC-01-01", "下列各项中，不属于会计基本假设的是", "币值稳定", ["会计主体", "持续经营", "货币计量"]),
        ("ACC-01-01", "权责发生制的基础是", "持续经营假设", ["会计主体假设", "货币计量假设", "会计分期假设"]),
        ("ACC-01-01", "会计信息质量要求中，要求企业提供的会计信息应当与财务报告使用者的经济决策需要相关的是", "相关性", ["可比性", "谨慎性", "及时性"]),
        ("ACC-01-01", "同一企业不同时期发生的相同或相似的交易或事项，应当采用一致的会计政策，这体现的是", "可比性", ["相关性", "实质重于形式", "重要性"]),
        ("ACC-01-01", "企业对交易或者事项进行会计确认、计量和报告应当保持应有的谨慎，这体现的是", "谨慎性", ["相关性", "可比性", "及时性"]),
        ("ACC-01-02", "资产按照预计从其持续使用和最终处置中所产生的未来净现金流量的折现金额计量，这种计量属性是", "可变现净值", ["历史成本", "重置成本", "公允价值"]),
        ("ACC-01-02", "负债按照预计期限内需要偿还的未来净现金流出量的折现金额计量，这种计量属性是", "现值", ["历史成本", "可变现净值", "公允价值"]),
        ("ACC-01-02", "下列各项中，引起资产和负债同时增加的是", "向银行借款", ["偿还应付账款", "收回应收账款", "用银行存款购买固定资产"]),
        ("ACC-01-02", "下列各项中，引起资产内部一增一减的是", "收回应收账款", ["向银行借款", "偿还应付账款", "赊购原材料"]),
        ("ACC-01-02", "下列各项中，引起所有者权益减少的是", "宣告分配现金股利", ["提取盈余公积", "资本公积转增资本", "盈余公积补亏"]),
        ("ACC-03-01", "存货入库前的挑选整理费用应", "计入存货成本", ["计入管理费用", "计入销售费用", "计入财务费用"]),
        ("ACC-03-01", "商品流通企业在采购商品过程中发生的运输费、装卸费等，应当", "计入存货成本", ["计入销售费用", "计入管理费用", "计入财务费用"]),
        ("ACC-03-02", "存货跌价准备应当", "在当期确认为资产减值损失", ["计入管理费用", "计入销售费用", "计入营业外支出"]),
        ("ACC-03-02", "存货跌价准备转回时，应当", "冲减资产减值损失", ["增加营业外收入", "增加公允价值变动损益", "增加其他业务收入"]),
        ("ACC-04-01", "下列各项中，不应计入固定资产成本的是", "固定资产投入使用后发生的日常修理费", ["购买价款", "相关税费", "安装费"]),
        ("ACC-04-01", "自营建造固定资产，工程完工前盘亏的工程物资，应", "计入工程成本", ["计入营业外支出", "计入管理费用", "计入其他业务支出"]),
        ("ACC-04-02", "下列固定资产中，不应计提折旧的是", "已提足折旧仍继续使用的固定资产", ["未使用的房屋", "经营租出的固定资产", "大修理停用的固定资产"]),
        ("ACC-04-02", "下列固定资产中，应计提折旧的是", "未使用的房屋及建筑物", ["已提足折旧仍使用的固定资产", "提前报废的固定资产", "经营租入的固定资产"]),
        ("ACC-16-01", "收入确认的五步法模型中，第一步是", "识别与客户订立的合同", ["识别履约义务", "确定交易价格", "分摊交易价格"]),
        ("ACC-16-01", "企业在履行履约义务的同时客户即取得并消耗企业履约所带来的利益，该履约义务属于", "在某一时段内履行", ["在某一时点履行", "不构成履约义务", "无法确定"]),
        # 审计
        ("AUD-01-01", "审计的保证程度是", "合理保证", ["绝对保证", "有限保证", "无保证"]),
        ("AUD-01-01", "下列不属于审计要素的是", "审计意见类型", ["审计业务三方关系人", "财务报表", "审计证据"]),
        ("AUD-01-01", "审计业务三方关系人不包括", "被审计单位的供应商", ["审计师", "管理层", "预期使用者"]),
        ("AUD-06-02", "下列关于审计证据充分性的说法，正确的是", "证据数量越多，充分性越高", ["证据质量越高，充分性越低", "充分性与数量无关", "充分性只取决于审计时间"]),
        ("AUD-06-02", "审计证据的可靠性受其来源影响，下列最可靠的证据是", "直接获取的外部证据", ["被审计单位提供的内部证据", "口头证据", "复印件"]),
        ("AUD-03-02", "下列审计程序中，能提供最可靠证据的是", "函证", ["询问", "观察", "分析程序"]),
        ("AUD-03-02", "下列属于审计程序的是", "重新计算", ["评估", "判断", "推测"]),
        ("AUD-06-02", "下列关于审计风险模型的说法，正确的是", "审计风险=重大错报风险×检查风险", ["审计风险=固有风险×控制风险", "检查风险=审计风险+重大错报风险", "重大错报风险=审计风险×检查风险"]),
        ("AUD-06-02", "注册会计师可以通过实施审计程序来控制的是", "检查风险", ["固有风险", "控制风险", "审计风险"]),
        ("AUD-07-02", "内部控制五要素中，基础是", "控制环境", ["风险评估", "控制活动", "信息与沟通"]),
        ("AUD-07-02", "下列属于内部控制活动的是", "职责分离", ["组织结构", "管理理念", "人力资源政策"]),
        ("AUD-07-02", "下列不属于内部控制缺陷的是", "控制运行完美无缺", ["设计不当", "未执行", "执行无效"]),
        # 财务成本管理
        ("FCM-01-03", "货币时间价值计算中，复利终值系数表示为", "(F/P, i, n)", ["(P/F, i, n)", "(F/A, i, n)", "(A/F, i, n)"]),
        ("FCM-01-03", "货币时间价值计算中，复利现值系数表示为", "(P/F, i, n)", ["(F/P, i, n)", "(F/A, i, n)", "(A/P, i, n)"]),
        ("FCM-01-03", "普通年金终值系数表示为", "(F/A, i, n)", ["(P/F, i, n)", "(F/P, i, n)", "(A/F, i, n)"]),
        ("FCM-01-03", "普通年金现值系数表示为", "(P/A, i, n)", ["(F/A, i, n)", "(P/F, i, n)", "(A/P, i, n)"]),
        ("FCM-01-03", "下列关于β系数的说法，正确的是", "β系数衡量系统性风险", ["β系数衡量非系统性风险", "β系数可以为负", "β系数等于0表示无风险"]),
        ("FCM-01-03", "β系数大于1表示", "该证券的风险高于市场平均风险", ["该证券的风险低于市场平均风险", "该证券无风险", "该证券风险等于市场平均"]),
        ("FCM-03-01", "债务资本成本是税后的，因为", "利息可以抵税", ["股利可以抵税", "债务不需要偿还", "债务没有风险"]),
        ("FCM-03-01", "下列关于资本成本的说法，正确的是", "资本成本是投资者要求的必要报酬率", ["资本成本是企业过去的融资成本", "资本成本与风险无关", "资本成本是会计成本"]),
        ("FCM-14-01", "盈亏平衡点的计算公式是", "固定成本÷(单价-单位变动成本)", ["固定成本÷单价", "变动成本÷(单价-固定成本)", "总收入÷总成本"]),
        ("FCM-14-01", "边际贡献等于", "销售收入-变动成本", ["销售收入-固定成本", "销售收入-总成本", "利润+固定成本"]),
        ("FCM-14-01", "安全边际等于", "实际销售量-盈亏平衡点销售量", ["实际销售量+盈亏平衡点销售量", "实际销售收入", "盈亏平衡点销售量"]),
        # 战略
        ("STR-05-01", "PEST分析中S代表", "社会环境", ["政治环境", "经济环境", "技术环境"]),
        ("STR-05-01", "PEST分析中T代表", "技术环境", ["政治环境", "经济环境", "社会环境"]),
        ("STR-02-03", "SWOT分析中W代表", "劣势(Weaknesses)", ["优势", "机会", "威胁"]),
        ("STR-02-03", "SWOT分析中T代表", "威胁(Threats)", ["优势", "劣势", "机会"]),
        ("STR-05-01", "下列属于密集型战略的是", "市场渗透战略", ["横向一体化", "相关多元化", "非相关多元化"]),
        ("STR-05-01", "下列属于一体化战略的是", "纵向一体化", ["市场渗透", "市场开发", "产品开发"]),
        ("STR-05-01", "下列不属于波特基本竞争战略的是", "集中差异化战略", ["成本领先战略", "差异化战略", "集中化战略"]),
        ("STR-05-01", "下列属于企业面临的市场风险的是", "汇率风险", ["法律风险", "运营风险", "战略风险"]),
        ("STR-05-01", "下列属于企业面临的运营风险的是", "流程风险", ["汇率风险", "利率风险", "商品价格风险"]),
        # 经济法
        ("LAW-05-01", "下列关于一人有限责任公司的说法，正确的是", "一个自然人只能投资设立一个一人有限责任公司", ["一人公司不设股东会", "一人公司注册资本无最低限额", "一人公司股东承担无限责任"]),
        ("LAW-05-01", "下列关于国有独资公司的说法，正确的是", "国有独资公司不设股东会", ["国有独资公司设股东会", "国有独资公司董事会成员由股东选举", "国有独资公司监事会成员全部由国务院委派"]),
        ("LAW-05-02", "有限责任公司董事会成员人数为", "3-13人", ["1-5人", "5-19人", "5-20人"]),
        ("LAW-05-02", "股份有限公司董事会成员人数为", "5-19人", ["3-13人", "1-5人", "5-20人"]),
        ("LAW-05-02", "下列关于监事会的说法，正确的是", "监事会成员不得少于3人", ["监事会成员不得少于5人", "董事可以兼任监事", "经理可以兼任监事"]),
        ("LAW-03-01", "要约的撤回发生在", "要约到达受要约人之前或同时", ["要约到达受要约人之后", "承诺作出之后", "合同成立之后"]),
        ("LAW-03-01", "要约的撤销发生在", "要约到达受要约人之后、承诺作出之前", ["要约到达受要约人之前", "承诺作出之后", "合同成立之后"]),
        ("LAW-03-01", "下列要约不得撤销的是", "要约人确定了承诺期限", ["要约未确定承诺期限", "受要约人未作出承诺", "要约已经到达"]),
        ("LAW-03-02", "当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担的违约责任不包括", "行政处罚", ["继续履行", "采取补救措施", "赔偿损失"]),
        ("LAW-03-02", "当事人既约定违约金又约定定金的，一方违约时", "对方可以选择适用违约金或定金条款", ["同时适用违约金和定金", "只能适用违约金", "只能适用定金"]),
        # 税法
        ("TAX-04-01", "增值税的类型不包括", "消费型增值税", ["生产型增值税", "收入型增值税", "消费型增值税"]),
        ("TAX-04-01", "我国目前实行的是", "消费型增值税", ["生产型增值税", "收入型增值税", "积累型增值税"]),
        ("TAX-02-02", "下列项目的进项税额准予抵扣的是", "购进农产品生产用原材料", ["用于集体福利的购进货物", "个人消费的购进货物", "非正常损失的购进货物"]),
        ("TAX-02-03", "下列项目的进项税额不得抵扣的是", "用于简易计税方法的购进货物", ["购进生产用原材料", "购进办公用固定资产", "购进销售用货物"]),
        ("TAX-04-01", "企业所得税的纳税年度为", "公历1月1日至12月31日", ["公历4月1日至次年3月31日", "公历7月1日至次年6月30日", "公历10月1日至次年9月30日"]),
        ("TAX-04-01", "企业所得税分月或分季预缴，应当自月份或季度终了之日起", "15日内" , ["10日内", "20日内", "30日内"]),
        ("TAX-04-01", "企业所得税年度汇算清缴，应当自年度终了之日起", "5个月内", ["3个月内", "4个月内", "6个月内"]),
        ("TAX-05-01", "下列所得不属于个人所得税综合所得的是", "财产租赁所得", ["工资薪金所得", "劳务报酬所得", "稿酬所得"]),
        ("TAX-05-01", "个人所得税综合所得按", "年" , ["月", "季", "次"]),
        ("TAX-05-01", "下列属于个人所得税专项附加扣除的是", "子女教育", ["商业保险费", "住房公积金", "基本养老保险"]),
    ]

    for kp_code, question, answer, wrongs in all_concepts:
        opts = list(zip(labels_4, [answer] + wrongs))
        content = f"{question}（　）。"
        result = _gen_single_choice(content, "A", f"相关科目基础知识。", 2, opts)
        _add_question(db, kps[kp_code], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count


def gen_judgments_batch5(db: Session, kps: dict[str, int]) -> int:
    """第五批判断题，覆盖各科目高频考点。"""
    count = 0

    all_judgments = [
        # 会计
        ("ACC-01-01", "会计核算以人民币为记账本位币，业务收支以人民币以外的货币为主的，可以选定其中一种货币作为记账本位币。", True, "记账本位币可以是外币，但财务报表应折算为人民币。"),
        ("ACC-01-01", "企业发生的各项利得和损失均影响当期损益。", False, "部分利得和损失计入其他综合收益，不影响当期损益。"),
        ("ACC-01-02", "所有者权益的来源包括所有者投入的资本、直接计入所有者权益的利得和损失、留存收益等。", True, "所有者权益包括实收资本、资本公积、盈余公积和未分配利润。"),
        ("ACC-01-02", "企业收到投资者投入的资本，超过其在注册资本中所占份额的部分，应当计入当期损益。", False, "超过部分应计入资本公积。"),
        ("ACC-03-01", "存货的采购成本包括购买价款、相关税费、运输费、装卸费、保险费以及其他可归属于存货采购成本的费用。", True, "采购成本包括所有使存货达到场所和状态发生的支出。"),
        ("ACC-03-02", "资产负债表日，存货应当按照成本与可变现净值孰低计量。", True, "存货跌价准备按成本高于可变现净值的差额计提。"),
        ("ACC-04-01", "自行建造固定资产的成本，由建造该项资产达到预定可使用状态前所发生的必要支出构成。", True, "包括工程用物资成本、人工成本、缴纳的相关税费等。"),
        ("ACC-04-02", "固定资产折旧方法一经确定，不得变更。", False, "每年年度终了应对折旧方法进行复核，如有改变应作为会计估计变更处理。"),
        ("ACC-16-01", "企业应当在履行了合同中的履约义务，即在客户取得相关商品控制权时确认收入。", True, "收入确认的核心原则是控制权转移。"),
        ("ACC-16-01", "企业已将商品所有权上的主要风险和报酬转移给购货方，应当在转移时确认收入。", True, "风险报酬转移是收入确认的重要判断标准。"),
        # 审计
        ("AUD-01-01", "鉴证业务包括审计业务、审阅业务和其他鉴证业务。", True, "鉴证业务分为三类。"),
        ("AUD-01-01", "审计报告的日期应当是审计工作完成日。", True, "审计报告日不应早于管理层签署财务报表的日期。"),
        ("AUD-06-02", "审计证据的充分性和适当性之间存在着密切联系，证据的适当性影响充分性。", True, "质量越高，需要的数量可能越少。"),
        ("AUD-03-02", "函证银行存款不仅可以证实存款余额，还可以证实借款余额。", True, "银行询证函包括存款和借款信息。"),
        ("AUD-06-02", "如果评估的重大错报风险较高，注册会计师应当更多地依赖控制测试。", False, "重大错报风险高时，应更多依赖实质性程序。"),
        ("AUD-07-02", "内部控制能够防止并发现所有错报。", False, "内部控制只能提供合理保证，不能防止所有错报。"),
        # 财务成本管理
        ("FCM-01-03", "名义利率是指包含了通货膨胀因素的利率。", True, "名义利率=实际利率+通货膨胀率。"),
        ("FCM-01-03", "在复利计算中，计息期越短，实际利率越高。", True, "计息频率越高，实际利率越大。"),
        ("FCM-01-03", "系统性风险可以通过投资组合分散。", False, "系统性风险无法通过分散投资消除。"),
        ("FCM-01-03", "非系统性风险可以通过投资组合分散。", True, "非系统性风险是特定公司或行业的风险。"),
        ("FCM-03-01", "加权平均资本成本是各种资本成本的加权平均值。", True, "权重可以按账面价值或市场价值确定。"),
        ("FCM-14-01", "在其他条件不变的情况下，固定成本越大，盈亏平衡点越高。", True, "固定成本越大，需要更多的销售量来弥补。"),
        # 战略
        ("STR-05-01", "宏观环境分析包括政治、经济、社会和技术四个方面。", True, "即PEST分析。"),
        ("STR-02-03", "SWOT分析中的机会和威胁属于内部环境因素。", False, "机会和威胁属于外部环境因素。"),
        ("STR-05-01", "多元化战略总是能够降低企业风险。", False, "过度多元化可能导致管理困难，反而增加风险。"),
        ("STR-05-01", "成本领先战略要求企业在研发、生产、销售等方面实现成本优势。", True, "成本领先是全面的成本优势。"),
        ("STR-05-01", "企业风险管理的基本目标是帮助企业识别和应对风险，实现企业目标。", True, "风险管理服务于企业战略目标。"),
        # 经济法
        ("LAW-05-01", "公司可以设立分公司，分公司不具有法人资格。", True, "分公司不独立承担民事责任。"),
        ("LAW-05-01", "子公司具有法人资格，依法独立承担民事责任。", True, "子公司是独立的法律主体。"),
        ("LAW-05-02", "股东会会议作出增加注册资本的决议，必须经代表过半数表决权的股东通过。", False, "修改注册资本属于特别决议事项，需三分之二以上表决权通过。"),
        ("LAW-03-01", "承诺生效的地点为合同成立的地点。", True, "合同成立地点以承诺生效地点为准。"),
        ("LAW-03-02", "当事人一方违约后，对方应当采取适当措施防止损失的扩大，没有采取适当措施致使损失扩大的，不得就扩大的损失要求赔偿。", True, "这是减损规则。"),
        # 税法
        ("TAX-04-01", "增值税一般纳税人和小规模纳税人的划分标准是年应税销售额。", True, "一般纳税人标准为年销售额超过500万元。"),
        ("TAX-02-02", "销售额是指纳税人发生应税行为向购买方收取的全部价款和价外费用，但不包括收取的销项税额。", True, "增值税是价外税。"),
        ("TAX-02-03", "购进固定资产的进项税额不得抵扣。", False, "自2009年起，我国实行消费型增值税，购进固定资产的进项税额可以抵扣。"),
        ("TAX-04-01", "企业发生的公益性捐赠支出，在年度利润总额12%以内的部分，准予在计算应纳税所得额时扣除。", True, "公益性捐赠有扣除限额。"),
        ("TAX-05-01", "居民个人的综合所得，以每一纳税年度的收入额减除费用六万元以及专项扣除、专项附加扣除和依法确定的其他扣除后的余额，为应纳税所得额。", True, "综合所得按年计税。"),
        ("TAX-05-01", "非居民个人取得的工资薪金所得，以每月收入额减除费用五千元后的余额为应纳税所得额。", True, "非居民按月计税。"),
    ]

    for kp_code, content, is_correct, explanation in all_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps[kp_code], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    return count

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

    prev = total
    total += gen_auditing(db, code_to_id)
    db.commit()

    prev = total
    total += gen_finance(db, code_to_id)
    db.commit()

    prev = total
    total += gen_strategy(db, code_to_id)
    db.commit()

    prev = total
    total += gen_law(db, code_to_id)
    db.commit()

    prev = total
    total += gen_tax(db, code_to_id)
    db.commit()

    # 第二批扩展题目
    prev = total
    total += gen_accounting_extra(db, code_to_id)
    db.commit()
    print(f"  会计(扩展): {total - prev} 题")

    prev = total
    total += gen_auditing_extra(db, code_to_id)
    db.commit()
    print(f"  审计(扩展): {total - prev} 题")

    prev = total
    total += gen_strategy_extra(db, code_to_id)
    db.commit()
    print(f"  战略(扩展): {total - prev} 题")

    prev = total
    total += gen_law_extra(db, code_to_id)
    db.commit()
    print(f"  经济法(扩展): {total - prev} 题")

    prev = total
    total += gen_tax_extra(db, code_to_id)
    db.commit()
    print(f"  税法(扩展): {total - prev} 题")

    # 第三批大规模扩展题目
    prev = total
    total += gen_accounting_batch3(db, code_to_id)
    db.commit()
    print(f"  会计(第三批): {total - prev} 题")

    prev = total
    total += gen_finance_batch3(db, code_to_id)
    db.commit()
    print(f"  财管(第三批): {total - prev} 题")

    prev = total
    total += gen_all_subjects_judgments(db, code_to_id)
    db.commit()
    print(f"  全科目判断题: {total - prev} 题")

    prev = total
    total += gen_all_subjects_concepts(db, code_to_id)
    db.commit()
    print(f"  全科目概念题: {total - prev} 题")

    prev = total
    total += gen_tax_batch3(db, code_to_id)
    db.commit()
    print(f"  税法(第三批): {total - prev} 题")

    # 第四批补充薄弱科目
    prev = total
    total += gen_auditing_batch4(db, code_to_id)
    db.commit()
    print(f"  审计(第四批): {total - prev} 题")

    prev = total
    total += gen_strategy_batch4(db, code_to_id)
    db.commit()
    print(f"  战略(第四批): {total - prev} 题")

    prev = total
    total += gen_law_batch4(db, code_to_id)
    db.commit()
    print(f"  经济法(第四批): {total - prev} 题")

    prev = total
    total += gen_accounting_batch4(db, code_to_id)
    db.commit()
    print(f"  会计(第四批): {total - prev} 题")

    # 第五批概念与判断题
    prev = total
    total += gen_concepts_batch5(db, code_to_id)
    db.commit()
    print(f"  概念题(第五批): {total - prev} 题")

    prev = total
    total += gen_judgments_batch5(db, code_to_id)
    db.commit()
    print(f"  判断题(第五批): {total - prev} 题")

    # 打乱所有题目的选项顺序，避免正确答案总在A
    shuffled = _shuffle_all_options(db)
    db.commit()
    print(f"  选项打乱: {shuffled} 题")

    # 为解析追加通俗化记忆口诀
    enhanced = _enhance_explanations(db)
    db.commit()
    print(f"  解析增强: {enhanced} 题")

    print(f"  ======================")
    print(f"  总计: {total} 题")
    return total


def _shuffle_all_options(db: Session) -> int:
    """
    打乱所有单选题的选项顺序，并更新 answer 字段。
    判断题只有2个固定选项(正确/错误)，也做随机交换。
    """
    questions = db.query(Question).all()
    labels_4 = ["A", "B", "C", "D"]
    labels_2 = ["A", "B"]
    count = 0

    for q in questions:
        opts = list(q.options)
        if len(opts) <= 1:
            continue

        # 找到正确选项
        correct_opt = None
        for o in opts:
            if o.is_correct:
                correct_opt = o
                break
        if correct_opt is None:
            continue

        # 随机打乱
        random.shuffle(opts)

        # 重新分配标签
        if len(opts) == 2:
            new_labels = labels_2
        elif len(opts) == 4:
            new_labels = labels_4
        else:
            new_labels = labels_4[:len(opts)]

        for i, opt in enumerate(opts):
            opt.label = new_labels[i]

        # 更新 answer 字段
        if q.question_type == "judgment":
            # 判断题的 answer 是 "正确"/"错误"，不需要改
            pass
        else:
            # 单选题的 answer 是选项标签
            q.answer = correct_opt.label

        count += 1

    return count


# ========== 解析增强：通俗化 + 记忆口诀 ==========

# 关键词 → 记忆口诀映射表
_MNEMONIC_RULES: list[tuple[str, str]] = [
    # --- 会计 ---
    ("坏账准备", "💡 记忆口诀：坏账准备 = 余额 × 比例，就像「按比例存钱防坏账」。应收越多、比例越高，准备金越多。"),
    ("所有者权益", "💡 记忆口诀：所有者权益 = 本钱(实收资本) + 存粮(盈余公积) + 余粮(未分配利润)。三大块加一起就是股东的家底。"),
    ("盈余公积", "💡 记忆口诀：盈余公积是从利润里「抠」出来存着防饥荒的，像「强制储蓄」。"),
    ("折旧", "💡 记忆口诀：折旧 = (原值 - 残值) ÷ 年限。把「能用多少年」分摊到每年，就像「切蛋糕」每人一份。残值是最后剩下的蛋糕底。"),
    ("双倍余额递减", "💡 记忆口诀：双倍余额 = 账面价值 × (2 ÷ 年限)。特点是「前期多折、后期少折」，像「吃苹果越吃越小」。最后两年改直线法收尾。"),
    ("年数总和", "💡 记忆口诀：年数总和法 = (原值-残值) × 尚可使用年数 ÷ 年数总和。分子越来越小，所以「折旧逐年递减」，像「下楼梯」。"),
    ("年限平均", "💡 记忆口诀：直线法最简单——每年折旧一样多，就像「均摊房租」，每月固定付一样。"),
    ("存货入账", "💡 记忆口诀：存货成本 = 买价 + 运费 + 挑选费。记住「买进来 + 运回来 + 整理好」三步走，增值税不算在内（可以抵扣）。"),
    ("加权平均", "💡 记忆口诀：加权平均 = 总花钱 ÷ 总数量。就像「混在一起算均价」，不管哪批买的，统统平均。"),
    ("营业收入", "💡 记忆口诀：含税价 ÷ (1+税率) = 不含税收人。增值税是「价外税」，要「扒掉税皮」才是真正的收入。"),
    ("营业利润", "💡 记忆口诀：营业利润 = 收入 - 成本 - 费用。简单说就是「赚的 - 花的 - 烧的」= 真正留在口袋的。"),
    ("借贷记账", "💡 记忆口诀：「有借必有贷，借贷必相等」。资产费用增加记借方，负债收入增加记贷方。借 = 左边进，贷 = 右边出。"),
    ("资产减值", "💡 记忆口诀：存货跌价 = 成本 vs 可变现净值，取低的。就像「旧手机估值」，能卖多少算多少，比买价低就要计提减值。"),

    # --- 审计 ---
    ("审计风险", "💡 记忆口诀：审计风险 = 重大错报风险 × 检查风险。就像「闯红灯被拍」= 你违规的概率 × 摄像头没拍到的概率。审计师只能控制「检查风险」。"),
    ("重要性水平", "💡 记忆口诀：重要性 = 基准 × 比例。就像「多少钱的错误你会介意」，金额越大越重要，小错误可以忽略。"),
    ("审计证据", "💡 记忆口诀：外部证据 > 内部证据，书面 > 口头。就像「银行流水」比「自己写的收据」可信，「签字盖章」比「口头说说」靠谱。"),
    ("内部控制", "💡 记忆口诀：内控五要素 = 环境是地基 + 风险评估是眼睛 + 控制活动是手脚 + 信息沟通是神经 + 监督是体检。缺一不可。"),
    ("函证", "💡 记忆口诀：函证 = 找第三方确认。银行确认存款借款，客户确认应收账款。第三方说的话最可信。"),
    ("控制测试", "💡 记忆口诀：控制测试 = 查「制度管不管用」。不是查具体数字对不对，而是查「流程有没有按规定执行」。"),
    ("实质性程序", "💡 记忆口诀：实质性程序 = 直接查数字对不对。函证、盘点、重新计算，都是「真刀真枪验真伪」。"),

    # --- 财务成本管理 ---
    ("WACC", "💡 记忆口诀：WACC = 借钱成本(税后) × 借钱比例 + 股东要求回报 × 股东比例。利息能抵税所以要「税后」，股利不能抵税。整体就是「融资的代价」。"),
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

    # --- 税法 ---
    ("销项税额", "💡 记忆口诀：销项税 = 不含税销售额 × 税率。卖东西收的税，是「你替税务局收的」，不是你的收入。"),
    ("进项税额", "💡 记忆口诀：进项税 = 买东西付的税，可以抵扣。买东西时「先垫的税」，卖东西时「收的税」来抵，差额上交。"),
    ("应纳增值税", "💡 记忆口诀：应交增值税 = 销项税 - 进项税。卖东西收的税减去买东西垫的税，差额就是「要上交国家的」。"),
    ("含税", "💡 记忆口诀：不含税价 = 含税价 ÷ (1+税率)。开发票要「扒掉税」看净额，就像「剥洋葱」去掉税那一层。"),
    ("企业所得税", "💡 记忆口诀：企业所得税 = 应纳税所得额 × 税率(一般25%)。应纳税所得额 ≠ 会计利润，要按税法调整。高新企业享15%优惠。"),
    ("个人所得税", "💡 记忆口诀：综合所得七级累进，3%→45%。「赚得越多税率越高」，先扣6万/年免征额，再扣专项附加。"),
    ("公益性捐赠", "💡 记忆口诀：公益捐赠限额 = 利润总额 × 12%。超过部分以后3年结转。做善事有上限，不是捐多少扣多少。"),

    # --- 战略 ---
    ("SWOT", "💡 记忆口诀：SWOT = 内部优劣(S/W) + 外部机威(O/T)。SO用优势抓机会，WT避免劣势遇威胁。"),
    ("波特五力", "💡 记忆口诀：五力 = 现有竞争者(内斗) + 新进入者(外来威胁) + 替代品(替代威胁) + 供应商议价 + 买方议价。五力越强行业越难赚。"),
    ("成本领先", "💡 记忆口诀：成本领先 = 做到行业最低成本。靠规模效应+精细管理，价格战时你最能扛。"),
    ("差异化", "💡 记忆口诀：差异化 = 做出别人做不到的特色。品牌、技术、服务独特，客户愿意付溢价。"),
    ("BCG矩阵", "💡 记忆口诀：BCG四象限——明星(高增长高份额，砸钱养)、现金牛(低增长高份额，挤奶用)、问题(高增长低份额，赌不赌)、瘦狗(双低，考虑扔)。"),
    ("PEST", "💡 记忆口诀：PEST = 政治(P) + 经济(E) + 社会(S) + 技术(T)。宏观环境四把刀，扫描外部大势用。"),
    ("风险接受", "💡 记忆口诀：风险接受 = 觉得风险太小懒得管。不是「不知道」，而是「知道但选择不管」，省事省钱。"),
    ("风险规避", "💡 记忆口诀：风险规避 = 不干了，直接退出。惹不起躲得起，比如不做某项业务。"),
    ("风险降低", "💡 记忆口诀：风险降低 = 内控+分散，把风险压到可接受。系安全带不等于不出事，但减轻后果。"),
    ("风险转移", "💡 记忆口诀：风险转移 = 买保险、外包，把风险甩给别人。花小钱让保险公司扛大雷。"),

    # --- 经济法 ---
    ("要约", "💡 记忆口诀：要约 = 「我正式提出条件，你同意就成交」。内容必须具体确定，有约束力。要约邀请只是「广告」，没有约束力。"),
    ("承诺", "💡 记忆口诀：承诺 = 「我同意你的条件」。承诺到达对方时合同成立。不能改条件，改了就是新要约。"),
    ("违约金", "💡 记忆口诀：违约金 = 合同约定赔多少就赔多少。过高可请求法院调低(超损失30%)，过低可调高。补偿为主，惩罚为辅。"),
    ("定金", "💡 记忆口诀：定金不超过合同额20%。收方违约双倍返还，付方违约不退。定金+违约金只能选一个，不能两个都要。"),
    ("有限责任公司", "💡 记忆口诀：有限公司股东≤50人，以出资额为限担责。不设股东会可(一人公司)，董事会3-13人。"),
    ("股份有限公司", "💡 记忆口诀：股份公司发起人2-200，全部资本分等额股份。董事会5-19人，可上市募集资本。"),

    # --- 通用 ---
    ("试算平衡", "💡 记忆口诀：试算平衡 = 借方合计 = 贷方合计。但平衡不代表全对，漏记、重记、记反方向都可能查不出。"),
    ("权责发生制", "💡 记忆口诀：权责发生制 = 不管钱收没收到，权利责任发生就记账。收付实现制才看「钱动没动」。"),
    ("谨慎性", "💡 记忆口诀：谨慎性 = 「不高估资产，不低估负债」。宁可少报利润不可多报，坏消息早报好消息晚报。"),
    ("实质重于形式", "💡 记忆口诀：实质重于形式 = 看经济实质不看法律形式。售后回购法律上卖了，经济上还是自己的，不确认收入。"),
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
        kp = q.knowledge_point
        kp_name = kp.name if kp else "综合知识点"

        # 考点直接使用知识点名称的映射，确保考点与题目内容一致
        q.exam_point = kp_to_exam_point.get(kp_name, kp_name)

        # 所有题目统一标记为模拟题（模板生成，非真实考题）
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


def _enhance_explanations(db: Session) -> int:
    """
    为每道题的解析追加通俗化记忆口诀。
    根据题目内容匹配关键词，追加对应的记忆技巧。
    """
    # 先为空知识点补充基础题目
    _fill_empty_knowledge_points(db)

    # 标注历年真题、考点
    _tag_exam_info(db)

    questions = db.query(Question).all()
    count = 0

    for q in questions:
        if not q.explanation:
            continue

        # 避免重复添加
        if "💡" in q.explanation:
            continue

        # 合并题干和解析作为匹配文本
        match_text = (q.content or "") + " " + (q.explanation or "")

        best_mnemonic = None
        for keyword, mnemonic in _MNEMONIC_RULES:
            if keyword in match_text:
                best_mnemonic = mnemonic
                break

        if best_mnemonic:
            q.explanation = q.explanation + "\n" + best_mnemonic
            count += 1
        else:
            # 没有匹配到口诀的，加通用提示
            q.explanation = q.explanation + "\n💡 小贴士：CPA考试重在理解原理，建议结合实际案例记忆，反复练习巩固。"
            count += 1

    return count
