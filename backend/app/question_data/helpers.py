"""
CPA 题库生成 - 底层工具函数。

提供知识点确保、题目添加、单选题/判断题构造、选项打乱与数值提取等通用工具，
供各科目题目生成器与数据库修复逻辑复用。
"""
import random

from sqlalchemy.orm import Session

from app.models import KnowledgePoint, Question, QuestionOption


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


def _shuffled_opts(
    correct: str, wrongs: list[str],
) -> tuple[str, list[tuple[str, str, bool]]]:
    """
    将正确答案和干扰项打乱并分配 A/B/C/D 标签。

    返回 (answer_label, [(label, content, is_correct), ...])。
    确保正确答案不总是第一个，消除答案分布偏斜。
    自动去重：跳过与正确答案或其他干扰项内容相同的项，不足时自动补充。
    """
    labels = ["A", "B", "C", "D", "E", "F"]
    # 去重：保持顺序，跳过重复内容
    seen = {correct}
    unique_wrongs = []
    for w in wrongs:
        if w not in seen:
            seen.add(w)
            unique_wrongs.append(w)
    # 不足3个干扰项时，自动补充数值偏移项（仅当正确答案是纯数值时）
    _base = _extract_number(correct) if _is_pure_numeric(correct) else None
    while len(unique_wrongs) < 3:
        if _base is not None:
            _offset = random.choice([1, -1, 2, -2, 10, -10, 100, -100, 0.5, -0.5])
            _fake = str(round(_base + _offset, 2) if isinstance(_base, float) else _base + _offset)
            if _fake not in seen:
                seen.add(_fake)
                unique_wrongs.append(_fake)
        else:
            break  # 文本型无法自动补充
    all_opts = [(correct, True)] + [(w, False) for w in unique_wrongs]
    random.shuffle(all_opts)
    answer_label = None
    result = []
    for i, (content, is_correct) in enumerate(all_opts):
        label = labels[i]
        if is_correct:
            answer_label = label
        result.append((label, content, is_correct))
    return answer_label, result


def _extract_number(s: str) -> float | None:
    """尝试从字符串中提取数值，用于自动补充干扰项。"""
    import re as _re
    m = _re.search(r'-?\d+\.?\d*', s.replace(',', ''))
    return float(m.group()) if m else None


def _is_pure_numeric(s: str) -> bool:
    """判断字符串是否为纯数值（不含中文/英文文字），用于决定是否生成数值型干扰项。

    避免对"借：原材料 50万元；贷：银行存款 50万元"这类文本选项
    生成纯数字干扰项（如"50.5"），导致选项类型混杂。
    """
    import re as _re
    s = s.strip()
    # 纯数值：可选正负号 + 数字 + 可选小数 + 可选百分号/万元等单位
    # 但不允许包含中文字符或"借"/"贷"等分录关键词
    if _re.search(r'[\u4e00-\u9fff]', s):
        return False
    # 纯数字或带百分号的数字
    return bool(_re.match(r'^-?\d+\.?\d*%?$', s))


def _gen_judgment(
    content: str, is_correct: bool, explanation: str, difficulty: int = 2,
) -> tuple[str, str, str, int, list[tuple[str, str, bool]]]:
    """构造判断题。"""
    answer = "正确" if is_correct else "错误"
    opts = [("A", "正确", is_correct), ("B", "错误", not is_correct)]
    return ("judgment", content, answer, explanation, difficulty, opts)

