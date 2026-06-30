"""
种子数据单元测试。

验证规范：
- seed_knowledge_points 创建正确的知识点数量和科目覆盖
- seed_knowledge_edges 创建正确的前置依赖关系
- seed_achievements 创建成就定义
- 重复调用 run_seed 是幂等的（不创建重复数据）
"""
import pytest

from app.models import (
    Achievement,
    KnowledgeEdge,
    KnowledgePoint,
    Question,
)
from app.seed_data import run_seed, seed_achievements, seed_knowledge_edges, seed_knowledge_points


class TestSeedKnowledgePoints:
    def test_creates_all_subjects(self, db_session):
        """种子数据应覆盖 CPA 全部 6 科目。"""
        code_to_id = seed_knowledge_points(db_session)
        subjects = set(
            db_session.query(KnowledgePoint.subject).distinct().all()
        )
        subject_names = {s[0] for s in subjects}
        assert "会计" in subject_names
        assert "审计" in subject_names
        assert "财务成本管理" in subject_names
        assert "公司战略与风险管理" in subject_names
        assert "经济法" in subject_names
        assert "税法" in subject_names

    def test_returns_code_to_id_mapping(self, db_session):
        """返回值应为 code -> id 的字典。"""
        code_to_id = seed_knowledge_points(db_session)
        assert len(code_to_id) > 0
        for code, kid in code_to_id.items():
            assert isinstance(code, str)
            assert isinstance(kid, int)
            kp = db_session.query(KnowledgePoint).filter(KnowledgePoint.id == kid).first()
            assert kp is not None
            assert kp.code == code

    def test_idempotent(self, db_session):
        """重复调用不应创建重复知识点。"""
        seed_knowledge_points(db_session)
        count1 = db_session.query(KnowledgePoint).count()
        seed_knowledge_points(db_session)
        count2 = db_session.query(KnowledgePoint).count()
        assert count1 == count2

    def test_kp_has_difficulty(self, db_session):
        """每个知识点应有 1-5 的难度值。"""
        seed_knowledge_points(db_session)
        kps = db_session.query(KnowledgePoint).all()
        for kp in kps:
            assert 1 <= kp.difficulty <= 5


class TestSeedKnowledgeEdges:
    def test_creates_edges(self, db_session):
        """应创建知识点依赖边。"""
        code_to_id = seed_knowledge_points(db_session)
        seed_knowledge_edges(db_session, code_to_id)
        edges = db_session.query(KnowledgeEdge).all()
        assert len(edges) > 0

    def test_edges_reference_valid_kps(self, db_session):
        """边的前置和后继都应指向有效知识点。"""
        code_to_id = seed_knowledge_points(db_session)
        seed_knowledge_edges(db_session, code_to_id)
        edges = db_session.query(KnowledgeEdge).all()
        kp_ids = set(code_to_id.values())
        for e in edges:
            assert e.source_id in kp_ids
            assert e.target_id in kp_ids


class TestRunSeed:
    def test_full_seed_creates_all_data(self, db_session):
        """run_seed 应创建知识点、边和成就。"""
        run_seed(db_session)
        assert db_session.query(KnowledgePoint).count() > 0
        assert db_session.query(KnowledgeEdge).count() > 0
        assert db_session.query(Achievement).count() > 0

    def test_run_seed_idempotent(self, db_session):
        """重复 run_seed 不应创建重复数据。"""
        run_seed(db_session)
        kp_count1 = db_session.query(KnowledgePoint).count()
        edge_count1 = db_session.query(KnowledgeEdge).count()
        ach_count1 = db_session.query(Achievement).count()

        run_seed(db_session)
        kp_count2 = db_session.query(KnowledgePoint).count()
        edge_count2 = db_session.query(KnowledgeEdge).count()
        ach_count2 = db_session.query(Achievement).count()

        assert kp_count1 == kp_count2
        assert edge_count1 == edge_count2
        assert ach_count1 == ach_count2
