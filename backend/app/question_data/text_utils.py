"""题库修复与解析增强共享的文本处理工具函数。

本模块提供纯粹的文本/题目解析辅助函数，供 ``module_builders`` 与
``fixes`` 复用。所有函数均为公开接口（无 ``_`` 前缀），不依赖数据库
写操作，仅做字符串/题目对象的只读解析与转换。
"""
import re

from app.models import Question

# 匹配解析中引用选项字母的模式。
# 形如 "A选项"、"A属于"、"A、"、"A（内容）"、"A(内容)"、"A多元化" 等，
# 即单个大写字母 A-D 紧跟"选项"二字、中文标点或任意中文字符。
OPTION_LETTER_RE = re.compile(r"[A-D](?:选项|[、，。（(]|[一-鿿])")

# 去重时可能追加的后缀（需在每次修复前清除，防止"（错误）（错误）"叠加）
DEDUP_SUFFIXES = ["（错误）", "（不正确）", "（非）", "（ variant）", "（变体1）", "（变体2）", "（变体3）"]


def strip_dedup_suffixes(content: str) -> str:
    """清除选项内容中累积的去重后缀。

    ``fix_existing_database`` 每次服务器启动时运行，如果上次运行追加了
    "（错误）" 等后缀来消重，下次运行可能再次追加导致 "（错误）（错误）"
    叠加。此函数在处理前先清除所有已知后缀，确保幂等。

    Args:
        content: 选项内容字符串。

    Returns:
        清除所有已知去重后缀后的内容（可能多次清除直到无后缀）。
    """
    changed = True
    while changed:
        changed = False
        for suffix in DEDUP_SUFFIXES:
            if content.endswith(suffix):
                content = content[: -len(suffix)]
                changed = True
    return content


def explanation_references_options(explanation: str) -> bool:
    """检测解析文本是否引用了选项字母（A/B/C/D）。

    若解析中包含选项字母引用，打乱选项顺序会导致解析中的字母指向
    与打乱后的选项内容错位，因此这类题目应跳过选项打乱。

    Args:
        explanation: 解析文本。

    Returns:
        若解析中存在形如 "A选项"、"B属于" 的选项字母引用则返回 True。
    """
    if not explanation:
        return False
    return bool(OPTION_LETTER_RE.search(explanation))


def extract_formula_and_result(explanation: str) -> tuple[str, str]:
    """从含「=」的计算型解析中提取文字公式与数值结果。

    解析常见形态如「销项税额=不含税销售额×适用税率=50×13%=6.5万元。」
    返回 ("销项税额=不含税销售额×适用税率", "6.5万元")：
    - 文字公式：等号左侧由汉字/运算符构成、不以数字开头的段落拼接；
    - 数值结果：最后一个以数字（含负号）开头的段落，去掉句末标点。
    无法提取时返回 ("", "")。

    Args:
        explanation: 解析文本。

    Returns:
        ``(文字公式, 数值结果)`` 二元组，无法提取时二者均为空串。
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


def extract_first_sentence(text: str) -> str:
    """提取文本的首句实质内容，跳过「该说法错误/正确」等通用前缀。

    Args:
        text: 原始文本。

    Returns:
        去除通用前缀并截取到首个句末标点前的首句内容。
    """
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


def extract_key_concept(content: str) -> str:
    """从题干中提取关键概念名词，用于概念题的通俗解释。

    Args:
        content: 题干文本。

    Returns:
        提取到的关键概念名词，无法提取时返回空串。
    """
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


def question_type_desc(qtype: str) -> str:
    """题型的人类可读描述。

    Args:
        qtype: 题型代码（如 ``single_choice``、``judgment``）。

    Returns:
        对应的中文名称，未知题型返回"题目"。
    """
    return {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "judgment": "判断题",
        "tbs": "综合题",
        "journal_entry": "会计分录题",
    }.get(qtype, "题目")


def is_calculation(q: Question) -> bool:
    """判断是否为计算型题目：解析中含「=」且能提取出文字公式。

    Args:
        q: 题目对象。

    Returns:
        若解析中可提取出文字公式则视为计算题，返回 True。
    """
    explanation = q.explanation or ""
    if "=" not in explanation:
        return False
    formula, _ = extract_formula_and_result(explanation)
    return bool(formula)


def question_anchor(q: Question) -> str:
    """生成题目专属的简洁锚点，用于区分同知识点/同关键词下的不同题目。

    优先级：计算题取「公式+结果」+题干数值 > 解析首句要点+题干数值 >
    题干关键概念+数值。返回不含句末标点的短语，无法提取时返回空串。

    Args:
        q: 题目对象。

    Returns:
        题目专属锚点短语，无法提取时返回空串。
    """
    explanation = q.explanation or ""
    content = q.content or ""
    key_nums = extract_key_numbers(content)

    if "=" in explanation:
        formula, result = extract_formula_and_result(explanation)
        if formula and result:
            base = f"公式为「{formula}」，结果{result}"
            if key_nums:
                return f"{base}，已知{key_nums}"
            return base
        if formula:
            return f"公式为「{formula}」"
    first = extract_first_sentence(explanation)
    if first:
        if key_nums:
            return f"要点为「{first}」，涉及{key_nums}"
        return f"要点为「{first}」"
    concept = extract_key_concept(content)
    if concept:
        if key_nums:
            return f"围绕「{concept}」，涉及{key_nums}"
        # 无数值时用题干片段
        snippet = content[:15].replace("（", "").replace("）", "").strip()
        return f"题干「{snippet}」"
    return ""


def extract_key_numbers(content: str) -> str:
    """从题干中提取关键数值（如金额、百分比、年份），用于差异化重复内容。

    Args:
        content: 题干文本。

    Returns:
        前 3 个有意义数值（含单位）以「、」连接的字符串，无数值时返回空串。
    """
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
