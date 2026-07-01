"""经济法科目题目生成器。"""
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


def gen_law(db: Session, kps: dict[str, int]) -> int:
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 1. 公司法数字类 ---
    company_numbers = [
        ("有限责任公司的股东人数上限为", "50", "50人以下", ["30", "100", "200"]),
        ("股份有限公司发起人人数下限为", "1", "1-200人（2023年新公司法）", ["2", "5", "10"]),
        ("股份有限公司发起人人数上限为", "200", "1-200人（2023年新公司法）", ["50", "100", "500"]),
        ("有限责任公司董事会成员人数为", "3人以上", "3人以上", ["2人以上", "5人以上", "7人以上"]),
        ("有限责任公司监事会成员不得少于", "3", "不少于3人", ["1", "2", "5"]),
        ("股东会年会应当在每年召开", "1次", "每年一次", ["2次", "半年1次", "季度1次"]),
        ("公司解散后清算组应当自成立之日起多少日内通知债权人", "10日", "10日内通知", ["5日", "15日", "30日"]),
        ("债权人申报债权的期限自接到通知书之日起不得少于", "30日", "不少于30日", ["15日", "45日", "60日"]),
        ("有限责任公司股东认缴出资的期限上限为", "5年", "5年", ["3年", "7年", "10年"]),
        ("上市公司董事会成员不得少于", "3人", "3人以上（2023年新公司法，独立董事占1/3以上）", ["5人", "7人", "9人"]),
    ]
    for question, answer, reason, wrongs in company_numbers:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"根据《公司法》，{question}（　）。"
        result = _gen_single_choice(content, "A", f"《公司法》规定{reason}。", 2, opts)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 2. 公司法判断题 ---
    law_judgments = [
        ("有限责任公司股东以其认缴的出资额为限对公司承担责任。", True, "有限责任原则。"),
        ("股份有限公司股东以其认购的股份为限对公司承担责任。", True, "有限责任原则。"),
        ("一人有限责任公司可以由自然人或法人设立。", True, "一人公司股东可以是自然人或法人。"),
        ("公司可以为股东提供担保。", True, "但需经股东会决议。"),
        ("公司法定代表人必须由董事长担任。", False, "2023新公司法：由代表公司执行公司事务的董事或者经理担任，不限于董事长。"),
        ("公司合并应当自作出决议之日起10日内通知债权人。", True, "公司法规定，公司合并应自作出决议之日起10日内通知债权人，并于30日内公告。"),
        ("股东有权查阅公司章程和股东会会议记录。", True, "股东知情权。"),
        ("公司分立前的债务由分立后的公司承担连带责任。", True, "除非另有约定。"),
        ("有限责任公司的股东之间可以相互转让其全部或部分股权。", True, "内部转让自由。"),
        ("股东向股东以外的人转让股权，应当经其他股东过半数同意。", False, "2023新公司法取消了过半数同意要求，改为书面通知制。其他股东自接到书面通知之日起满三十日未答复的，视为放弃优先购买权。"),
    ]
    for content, is_correct, explanation in law_judgments:
        result = _gen_judgment(content, is_correct, explanation, 2)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 3. 公司治理结构 ---
    governance = [
        ("选举和更换董事、监事", "股东会", "股东会职权（2023新公司法）"),
        ("决定公司的经营计划和投资方案", "董事会", "董事会职权（2023新公司法）"),
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


def gen_law_extra(db: Session, kps: dict[str, int]) -> int:
    """经济法扩展题目。"""
    count = 0
    labels = ["A", "B", "C", "D"]

    # --- 公司法数字题（扩展）---
    extra_numbers = [
        ("有限责任公司董事会成员人数为", "3人以上", ["2人以上", "5人以上", "7人以上"]),
        ("股份有限公司董事会成员人数为", "3人以上", ["2人以上", "5人以上", "7人以上"]),
        ("监事会的职工代表比例不得低于", "1/3", ["1/2", "1/4", "1/5"]),
        ("有限责任公司股东认缴出资的期限不得超过", "5年", ["3年", "7年", "10年"]),
        ("股东会临时会议应由代表多少以上表决权的股东提议", "1/10", ["1/3", "1/2", "1/4"]),
        ("董事会临时会议应由多少以上董事提议", "1/3", ["1/10", "1/2", "1/4"]),
        ("公司法定公积金转增资本后留存的部分不得少于转增前注册资本的", "25%", ["10%", "50%", "30%"]),
        ("公司提取法定公积金的比例为税后利润的", "10%", ["5%", "15%", "20%"]),
        ("法定公积金累计达到注册资本的多少以上可以不再提取", "50%", ["30%", "25%", "100%"]),
        ("公司分配当年税后利润前应先弥补亏损和", "提取法定公积金", ["缴纳税款", "支付股利", "计提坏账准备"]),
        ("公司公开发行股份前已发行的股份自上市交易之日起多长时间内不得转让", "1年", ["6个月", "2年", "3年"]),
        ("董事、监事、高级管理人员在任职期间每年转让的股份不得超过其所持股份的", "25%", ["10%", "50%", "100%"]),
        ("股东会作出修改公司章程的决议需经多少以上表决权通过", "2/3", ["1/2", "3/4", "1/3"]),
    ]
    for question, answer, wrongs in extra_numbers:
        opts = list(zip(labels, [answer] + wrongs))
        content = f"根据《公司法》，{question}（　）。"
        result = _gen_single_choice(content, "A", f"《公司法》相关规定。", 3, opts)
        _add_question(db, kps["LAW-05-01"], result[0], result[1], result[2], result[3], result[4], "mock", result[5])
        count += 1

    # --- 公司治理选择题（扩展）---
    gov_choices = [
        ("下列属于股东会职权的是", "选举和更换董事、监事", ["决定公司内部管理机构设置", "检查公司财务", "制定具体规章制度"]),
        ("下列属于董事会职权的是", "决定公司的经营计划和投资方案", ["选举和更换董事", "检查公司财务", "制定公司章程"]),
        ("下列属于监事会职权的是", "检查公司财务", ["决定经营方针", "聘任经理", "决定投资计划"]),
        ("下列属于经理职权的是", "组织实施公司年度经营计划", ["决定经营方针", "召集股东会", "检查公司财务"]),
        ("股东会的表决权按", "出资比例", ["股东人数", "董事人数", "职位高低"]),
        ("股份有限公司股东会的表决权按", "股份比例", ["股东人数", "职位高低", "出资额"]),
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
        content = f"根据《民法典》合同编，{question}（　）。"
        result = _gen_single_choice(content, "A", f"《民法典》合同编相关规定。", 3, opts)
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["LAW-03-02"], "single_choice", content, _ans,
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["LAW-03-02"], "single_choice", content, _ans,
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
            random.shuffle(all_opts)
            opts_data2 = [(labels_4[i], all_opts2[i][0], all_opts2[i][1]) for i in range(min(4, len(all_opts2)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["LAW-03-02"], "single_choice", content2, _ans,
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
            random.shuffle(all_opts)
            opts_data = [(labels_4[i], all_opts[i][0], all_opts[i][1]) for i in range(min(4, len(all_opts)))]
            _ans = labels_4[next(i for i, o in enumerate(all_opts) if o[1])]
            _add_question(db, kps["LAW-05-01"], "single_choice", content, _ans,
                          f"每名股东出资额=注册资本÷股东人数={cap}÷{sc}={per_capital}万元。", 2, "mock", opts_data)
            count += 1

    return count

