"""会计科目题目生成器。"""
import itertools
import random

from sqlalchemy.orm import Session

from app.question_data.helpers import (
    _add_question,
    _ensure_kp,
    _gen_judgment,
    _gen_single_choice,
    _shuffled_opts,
)


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
        wrong2_credit = "预付账款" if acct_debit != "预付账款" else "应收账款"
        wrong2 = f"借：{acct_debit} {amt}万元；贷：{wrong2_credit} {amt}万元"
        # wrong3 借方使用与正确项不同的科目，避免与正确项重复
        wrong3_debit = "长期借款" if acct_debit == "短期借款" else "短期借款"
        wrong3 = f"借：{wrong3_debit} {amt}万元；贷：{acct_credit} {amt}万元"
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
                # 生成干扰项并按数值去重，避免与正确答案或其他干扰项数值重复（如 total 与 price+tax 同为 113）
                correct_val = round(float(total), 1)
                wrong_candidates = [round(price + tax, 1), float(price), round(price + tax + freight + sort_fee, 1)]
                seen = {correct_val}
                wrong_vals = []
                for _w in wrong_candidates:
                    _val = round(float(_w), 1)
                    _tries = 0
                    while _val in seen and _tries < 50:
                        _tries += 1
                        _val = round(_val + 1, 1)
                    seen.add(_val)
                    wrong_vals.append(_val)
                _ans, opts_data = _shuffled_opts(str(total), [str(wrong_vals[0]), str(wrong_vals[1]), str(wrong_vals[2])])
                _add_question(db, kps["ACC-03-01"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["ACC-04-02"], "single_choice", content, _ans,
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
            for discount in [0.05, 0.10, 0.15]:
                revenue = round(unit_price * qty * (1 - discount), 1)
                disc_text = f"，商业折扣{int(discount*100)}%" if discount > 0 else ""
                content = f"某企业销售产品{qty}件，单价{unit_price}元{disc_text}。确认的收入金额为（　）元。"
                _ans, opts_data = _shuffled_opts(str(revenue), [str(unit_price * qty), str(round(unit_price * qty * (1 + 0.13), 1)), str(round(revenue * 0.87, 1))])
                _add_question(db, kps["ACC-16-01"], "single_choice", content, _ans,
                              f"收入=单价×数量×(1-折扣)={unit_price}×{qty}×{1-discount}={revenue}元。",
                              3, "mock", opts_data)
                count += 1

    return count


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
    nv_rates = [0.8, 0.9, 0.95, 1.05, 1.15, 1.2]
    for cost in costs:
        for nv_rate in nv_rates:
            nv = round(cost * nv_rate, 1)
            if nv < cost:
                provision = round(cost - nv, 1)
                content = f"某存货成本{cost}万元，可变现净值{nv}万元。应计提存货跌价准备（　）万元。"
                answer = str(provision)
                wrongs = [str(0), str(round(cost + nv, 1)), str(round(nv, 1))]
                opts_data = [("A", answer, True)] + [(labels[i+1], wrongs[i], False) for i in range(3)]
                random.shuffle(opts_data)
                _ans = next(o[0] for o in opts_data if o[2])
                _add_question(db, kps["ACC-03-02"], "single_choice", content, _ans,
                              f"成本{cost}>可变现净值{nv}，计提跌价准备={cost}-{nv}={provision}万元。", 3, "mock", opts_data)
            else:
                content = f"某存货成本{cost}万元，可变现净值{nv}万元。应计提存货跌价准备（　）万元。"
                wrongs = [str(round(nv - cost, 1)), str(round(cost * 0.1, 1)), str(round(nv, 1))]
                opts_data = [("A", "0", True)] + [(labels[i+1], wrongs[i], False) for i in range(3)]
                random.shuffle(opts_data)
                _ans = next(o[0] for o in opts_data if o[2])
                _add_question(db, kps["ACC-03-02"], "single_choice", content, _ans,
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
                # 按数值去重，避免运输费与安装费相等时两个干扰项数值相同
                correct_val = float(total)
                wrong_candidates = [float(price), float(price + tf), float(price + inst)]
                seen = {correct_val}
                wrong_vals = []
                for _w in wrong_candidates:
                    _val = round(float(_w), 1)
                    _tries = 0
                    while _val in seen and _tries < 50:
                        _tries += 1
                        _val = round(_val + 1, 1)
                    seen.add(_val)
                    wrong_vals.append(_val)
                opts_data = [("A", str(total), True)] + [(labels[i+1], str(wrong_vals[i]), False) for i in range(3)]
                random.shuffle(opts_data)
                _ans = next(o[0] for o in opts_data if o[2])
                _add_question(db, kps["ACC-04-01"], "single_choice", content, _ans,
                              f"固定资产入账价值=买价+运输费+安装费={price}+{tf}+{inst}={total}万元。", 3, "mock", opts_data)
                count += 1

    return count


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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["ACC-04-02"], "single_choice", content, _ans,
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
            random.shuffle(all_opts)
            opts_data2 = [(labels_4[i], all_opts2[i][0], all_opts2[i][1]) for i in range(min(4, len(all_opts2)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts2) if o[1])]
            _add_question(db, kps["ACC-04-02"], "single_choice", content2, _ans,
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["ACC-04-02"], "single_choice", content, _ans,
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
        content = "某企业分批购入存货："
        for i, (p, q) in enumerate(batches):
            content += f"第{i+1}批{q}件单价{p}元；"
        content += "采用加权平均法，存货单位成本为（　）元。"
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
        random.shuffle(all_opts)
        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
        _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
        _add_question(db, kps["ACC-03-01"], "single_choice", content, _ans,
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["ACC-03-01"], "single_choice", content, _ans,
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["ACC-16-01"], "single_choice", content, _ans,
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
                # 第三个干扰项用"只减一半费用"，避免 er=0.10 时 rev-cost == profit+rev*0.1 的重复
                wrongs = [str(round(rev - cost, 2)), str(round(rev - expense, 2)), str(round(rev - cost - expense * 0.5, 2))]
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["ACC-01-02"], "single_choice", content, _ans,
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
                random.shuffle(all_opts)
                opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                _add_question(db, kps["ACC-01-02"], "single_choice", content, _ans,
                              f"所有者权益=实收资本+未分配利润+盈余公积={cap}+{ret}+{sur}={equity}万元。", 3, "mock", opts_data)
                count += 1

    return count

