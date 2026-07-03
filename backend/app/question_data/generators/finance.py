"""财务成本管理科目题目生成器。"""
import random

from sqlalchemy.orm import Session

from app.question_data.helpers import (
    _add_question,
    _ensure_kp,
    _gen_judgment,
)


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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["FCM-01-02"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["FCM-01-02"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["FCM-01-02"], "single_choice", content, _ans,
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
                    random.shuffle(all_opts)
                    opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                    _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                    _add_question(db, kps["FCM-03-01"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["FCM-14-01"], "single_choice", content, _ans,
                              f"盈亏平衡点=固定成本/(单价-单位变动成本)={fixed_cost}/({price}-{var_cost})={int(bep)}件。",
                              3, "mock", opts_data)
                count += 1

    # --- 6. 风险与报酬判断题 ---
    risk_judgments = [
        ("系统性风险可以通过投资组合分散。", False, "系统性风险（市场风险）无法分散。"),
        ("非系统性风险可以通过投资组合分散。", True, "非系统性风险（特定风险）可分散。"),
        ("β系数衡量的是系统性风险。", True, "β反映个别资产相对市场的波动。"),
        ("β系数大于1表示该资产风险低于市场。", False, "β>1表示风险高于市场。"),
        ("β系数等于0表示该资产无系统性风险。", True, "β=0的资产与市场无关，无系统性风险，但仍可能有非系统性风险。"),
        ("期望报酬率是各种可能报酬率的加权平均。", True, "以概率为权重的加权平均。"),
        ("标准差是衡量总风险的指标。", True, "标准差反映离散程度。"),
        ("资本资产定价模型（CAPM）用于计算必要报酬率。", True, "CAPM: E(R)=Rf+β×(Rm-Rf)。"),
    ]
    for content, is_correct, explanation in risk_judgments:
        result = _gen_judgment(content, is_correct, explanation, 3)
        _add_question(db, kps["FCM-01-03"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
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
                        random.shuffle(all_opts)
                        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                        _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                        _add_question(db, kps["FCM-03-01"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["FCM-02-01"], "single_choice", content, _ans,
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
                random.shuffle(all_opts2)
                opts_data2 = [(labels_4[i], all_opts2[i][0], all_opts2[i][1]) for i in range(min(4, len(all_opts2)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts2) if o[1])]
                _add_question(db, kps["FCM-02-01"], "single_choice", content2, _ans,
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

