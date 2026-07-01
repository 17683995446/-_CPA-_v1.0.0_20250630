"""税法科目题目生成器。"""
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


def gen_tax(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 增值税销项税额计算 ---
    vat_rates = [13, 9, 6]
    revenues = [50, 100, 200, 300, 500, 800, 1000, 2000, 5000, 10000]
    for rate in vat_rates:
        for revenue in revenues:
            output_tax = round(revenue * rate / 100, 2)
            if rate == 6:
                content = f"某一般纳税人企业提供现代服务取得不含税销售额{revenue}万元，适用税率{rate}%。增值税销项税额为（　）万元。"
            elif rate == 9:
                content = f"某一般纳税人企业销售农产品取得不含税销售额{revenue}万元，适用税率{rate}%。增值税销项税额为（　）万元。"
            else:
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, _ans,
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, _ans,
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
                    random.shuffle(all_opts)
                    opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                    _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                    _add_question(db, kps["TAX-04-01"], "single_choice", content, _ans,
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
                    # 应纳增值税为0时，以销项税/进项税为基数生成干扰项，避免 random.uniform(0,0) 无法补足4个选项
                    _base = payable_val if payable_val > 0 else max(output_tax, input_tax, 1.0)
                    while len(all_opts) < 4 and _attempts < 200:
                        _attempts += 1
                        fake = round(_base + random.uniform(-_base*0.3, _base*0.3), 2)
                        fake_str = str(fake)
                        if fake_str not in seen and fake >= 0:
                            all_opts.append((fake_str, False))
                            seen.add(fake_str)
                    labels_4 = ["A", "B", "C", "D"]
                    random.shuffle(all_opts)
                    opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
                    _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
                    _add_question(db, kps["TAX-02-02"], "single_choice", content, _ans,
                                  f"应纳增值税=销项税额-进项税额={output_tax}-{input_tax}={payable_val}万元。",
                                  4, "mock", opts_data)
                    count += 1

    # --- 企业所得税税额计算 ---
    taxable_incomes = [50, 100, 200, 300, 500, 800, 1000, 2000, 3000, 5000, 10000, 20000]
    rates_tax = [0.25, 0.20, 0.15]
    rate_labels = {0.25: "25%", 0.20: "20%（小型微利企业）", 0.15: "15%（高新技术企业）"}
    for income in taxable_incomes:
        for rate in rates_tax:
            # 小型微利企业仅适用于年应纳税所得额不超过300万元的情形
            if rate == 0.20 and income > 300:
                continue
            if rate == 0.20:
                # 2023-2027年政策：应纳税所得额减按25%计入，按20%税率缴纳，实际有效税率5%
                tax = round(income * 0.25 * 0.20, 2)
                wrongs = [
                    str(round(income * 0.20, 2)),
                    str(round(income * 0.25, 2)),
                    str(round(income * 0.10, 2)),
                ]
            else:
                tax = round(income * rate, 2)
                wrongs = [
                    str(round(income * (rate + 0.05), 2)),
                    str(round(income * (rate - 0.05), 2)),
                    str(round(income * 0.1, 2)),
                ]
            content = f"某企业应纳税所得额{income}万元，适用税率{rate_labels[rate]}。应纳企业所得税为（　）万元。"
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            if rate == 0.20:
                _expl = f"小型微利企业应纳税额=应纳税所得额×25%×20%={income}×25%×20%={tax}万元。"
            else:
                _expl = f"应纳税额=应纳税所得额×税率={income}×{rate_labels[rate]}={tax}万元。"
            _add_question(db, kps["TAX-04-01"], "single_choice", content, _ans,
                          _expl,
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
        random.shuffle(all_opts)
        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
        _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
        _add_question(db, kps["TAX-05-01"], "single_choice", content, _ans,
                      f"应纳税所得额={income}-5000={taxable}元，按超额累进税率计算，应纳税额={tax}元。",
                      4, "mock", opts_data)
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
            if rate == 6:
                biz_desc = "提供现代服务"
            elif rate == 9:
                biz_desc = "销售农产品"
            else:
                biz_desc = "销售货物"
            content = f"某企业{biz_desc}不含税金额{amt}万元，增值税税率{rate}%。该笔业务的销项税额为（　）万元。"
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, _ans,
                          f"销项税额=不含税销售额×税率={amt}×{rate}%={tax}万元。", 3, "mock", opts_data)
            count += 1

    # --- 2. 含税销售额换算 ---
    for rate in rates:
        for amt in [113, 226, 339, 565, 1090, 1130, 2180, 3270, 5450, 10900]:
            tax = round(amt / (1 + rate / 100) * rate / 100, 2)
            if rate == 6:
                biz_desc = "提供现代服务"
            elif rate == 9:
                biz_desc = "销售农产品"
            else:
                biz_desc = "销售货物"
            content = f"某企业{biz_desc}含税金额{amt}万元，增值税税率{rate}%。该笔业务的不含税销售额为（　）万元。"
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["TAX-02-02"], "single_choice", content, _ans,
                          f"不含税销售额=含税销售额÷(1+税率)={amt}÷(1+{rate}%)={answer}万元。", 3, "mock", opts_data)
            count += 1

    # --- 3. 企业所得税应纳税额（更多组合） ---
    incomes = [20, 30, 50, 60, 80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000, 20000, 25000]
    rates_cit = [(0.25, "25%"), (0.20, "20%"), (0.15, "15%"), (0.10, "10%（预提所得税率）")]
    for income in incomes:
        for rate_val, rate_label in rates_cit:
            if rate_val == 0.10:
                # 非居民企业取得股息红利等，未在中国境内设立机构场所，按收入全额适用10%预提所得税率
                tax = round(income * 0.10, 2)
                content = f"某非居民企业取得来源于中国境内的股息红利{income}万元（未在中国境内设立机构场所），适用预提所得税率10%。应纳预提所得税为（　）万元。"
                wrongs = [str(round(income * 0.25, 2)), str(round(income * 0.05, 2)),
                          str(round(income * 0.15, 2))]
                expl = f"非居民企业取得来源于中国境内的股息红利，未在中国境内设立机构场所的，按收入全额适用10%预提所得税率。应纳预提所得税={income}×10%={tax}万元。"
            else:
                tax = round(income * rate_val, 2)
                content = f"某企业应纳税所得额{income}万元，适用企业所得税税率{rate_label}。应纳企业所得税为（　）万元。"
                wrongs = [str(round(income * (rate_val + 0.05), 2)), str(round(income * (rate_val - 0.05), 2)),
                          str(round(income * 0.1, 2))]
                expl = f"应纳税额=应纳税所得额×税率={income}×{rate_label}={tax}万元。"
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["TAX-04-01"], "single_choice", content, _ans,
                          expl, 3, "mock", opts_data)
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
        random.shuffle(all_opts)
        opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
        _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
        _add_question(db, kps["TAX-05-01"], "single_choice", content, _ans,
                      f"按七级超额累进税率计算（适用{level}），应纳税额={tax}元。", 4, "mock", opts_data)
        count += 1

    return count

