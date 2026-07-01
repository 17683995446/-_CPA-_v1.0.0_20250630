"""公司战略与风险管理科目题目生成器。"""
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
        random.shuffle(opts_list)
        _ans = next(o[0] for o in opts_list if o[2])
        content = f"{scenario}，这属于（　）。"
        _add_question(db, kps["STR-05-01"], "single_choice", content, _ans,
                      f"{scenario}属于{correct_type}中的{detail}。", 3, "mock", opts_list)
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
        content = f"下列活动中，属于基本活动的是（　）。{desc}对应的活动是："
        result = _gen_single_choice(content, "A", f"{desc}属于基本活动中的{activity}。", 3, opts)
        _add_question(db, kps["STR-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    for activity, desc in support_activities:
        wrong_activities = [a[0] for a in value_chain[:3]]
        opts = list(zip(labels, [activity] + wrong_activities))
        content = f"下列活动中，属于支持活动的是（　）。{desc}对应的活动是："
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

