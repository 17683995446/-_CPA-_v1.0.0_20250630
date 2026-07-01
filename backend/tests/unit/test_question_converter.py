"""
question_to_response 转换函数单元测试。

验证规范：
- 正确转换 ORM Question 到 QuestionResponse
- 选项正确映射
- exam_year 和 exam_point 字段正确传递
"""
import pytest

from app.models import KnowledgePoint, Question, QuestionOption
from app.schemas.question import QuestionResponse, question_to_response


@pytest.fixture
def sample_question(db_session):
    """创建带选项的测试题目。"""
    kp = KnowledgePoint(
        code="TEST-01",
        name="测试知识点",
        subject="会计",
        chapter="第一章",
        difficulty=3,
    )
    db_session.add(kp)
    db_session.flush()

    q = Question(
        knowledge_point_id=kp.id,
        question_type="single_choice",
        content="测试题目内容",
        answer="B",
        explanation="测试解析",
        difficulty=4,
        source="past_exam",
        exam_year=2023,
        exam_point="存货的初始计量与期末计量",
    )
    db_session.add(q)
    db_session.flush()

    for label, content, is_correct in [
        ("A", "选项A", False),
        ("B", "选项B", True),
        ("C", "选项C", False),
        ("D", "选项D", False),
    ]:
        opt = QuestionOption(
            question_id=q.id,
            label=label,
            content=content,
            is_correct=is_correct,
        )
        db_session.add(opt)

    db_session.commit()
    db_session.refresh(q)
    return q


class TestQuestionToResponse:
    def test_basic_conversion(self, sample_question):
        """基本字段正确转换。"""
        resp = question_to_response(sample_question)
        assert isinstance(resp, QuestionResponse)
        assert resp.content == "测试题目内容"
        assert resp.answer == "B"
        assert resp.difficulty == 4
        assert resp.question_type == "single_choice"

    def test_options_mapped(self, sample_question):
        """选项正确映射。注意：is_correct 字段不在响应中（防泄露）。"""
        resp = question_to_response(sample_question)
        assert len(resp.options) == 4
        labels = [o.label for o in resp.options]
        assert "A" in labels
        assert "B" in labels
        # is_correct 已从响应中移除，防止前端泄露答案
        for opt in resp.options:
            assert hasattr(opt, 'label')
            assert hasattr(opt, 'content')
            assert not hasattr(opt, 'is_correct')

    def test_exam_metadata(self, sample_question):
        """真题元数据正确传递。"""
        resp = question_to_response(sample_question)
        assert resp.source == "past_exam"
        assert resp.exam_year == 2023
        assert resp.exam_point == "存货的初始计量与期末计量"

    def test_variant_id_generated(self, sample_question):
        """variant_id 应基于数据库 ID 生成。"""
        resp = question_to_response(sample_question)
        assert resp.variant_id == f"db_{sample_question.id}"
