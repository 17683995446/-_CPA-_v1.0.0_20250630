"""审计科目题目生成器。"""
import random

from sqlalchemy.orm import Session

from app.question_data.helpers import (
    _add_question,
    _ensure_kp,
    _extract_number,
    _gen_judgment,
    _gen_single_choice,
    _is_pure_numeric,
    _shuffled_opts,
)


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
        _add_question(db, kps["AUD-03-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["AUD-06-02"], "single_choice", content, _ans,
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
        # 干扰项只从可靠性等级不同的类型中选取，避免多个证据类型共享同一等级而出现多个正确答案
        wrong_types = [e[0] for e in evidence_types if e[1] != reliability][:3]
        opts2 = list(zip(labels, [ev_type] + wrong_types))
        content = f"下列审计证据中，可靠性为「{reliability}」的是（　）。"
        result = _gen_single_choice(content, "A", f"{reason}。", 3, opts2)
        _add_question(db, kps["AUD-03-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
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
        ("审计准则要求注册会计师保持职业怀疑态度", True, "职业怀疑要求注册会计师对可能表明存在错报的迹象保持警觉，不轻信管理层声明，对获取的审计证据进行批判性评价。"),
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


def gen_auditing_batch4(db: Session, kps: dict[str, int]) -> int:
    """审计第四批：抽样、重要性、审计意见。"""
    count = 0
    labels_4 = ["A", "B", "C", "D"]

    # --- 1. 审计抽样样本量计算 ---
    # 使用属性抽样标准方法：5%信赖过度风险下，Poisson系数≈3.0
    # n ≈ R / (可容忍偏差率 - 预期偏差率)，R=3.0（5%风险）
    populations = [1000, 2000, 5000, 10000, 20000, 50000]
    tolerable_rates = [0.02, 0.05, 0.10]
    expected_rates = [0.00, 0.01, 0.02]
    for pop in populations:
        for tr in tolerable_rates:
            for er in expected_rates:
                if er >= tr:
                    continue
                # 属性抽样样本量：5%信赖过度风险，Poisson系数3.0
                import math
                n = max(25, int(math.ceil(3.0 / (tr - er))))
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["AUD-04-01"], "single_choice", content, _ans,
                              f"属性抽样样本量（5%信赖过度风险）：n ≈ 3.0 ÷（可容忍偏差率-预期偏差率）= 3.0÷({tr*100:.0f}%-{er*100:.0f}%)≈{n}个。", 5, "mock", opts_data)
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["AUD-02-02"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["AUD-06-02"], "single_choice", content, _ans,
                              f"检查风险=审计风险/重大错报风险={ar}/({ir}×{cr})={dr}。", 5, "mock", opts_data)
                count += 1

    return count

