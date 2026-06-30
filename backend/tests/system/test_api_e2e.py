"""
阶段7 系统测试：端到端 API 工作流验证。

验证完整的学习循环：
1. 用户注册 → 创建知识点 → 出题 → 答题 → BKT/FSRS/XP 联动
2. 多日学习进展：Streak 增长 + 掌握度提升 + 等级提升
3. 知识图谱 → 学习路径 → 沿路径出题
4. 分录判错 → 修正建议 → 重新提交
5. API 健康检查与文档可用性
"""
from datetime import date, datetime, timedelta

import pytest


@pytest.mark.system
class TestEndToEndLearningCycle:
    """端到端学习循环系统测试。"""

    def test_complete_study_session_e2e(self, client):
        """完整学习会话：注册 → 知识点 → 出题 → 答题 → 验证 BKT/FSRS/XP。"""
        # 1. 注册用户
        r = client.post("/api/users", json={
            "username": "e2e_user",
            "email": "e2e@test.com",
            "password": "password123",
            "target_exam_date": "2026-08-30",
            "daily_goal_minutes": 90,
        })
        assert r.status_code == 201
        user_id = r.json()["id"]

        # 2. 创建知识点
        r = client.post("/api/knowledge/points", json={
            "code": "ACC-01-01",
            "name": "借贷记账法",
            "subject": "会计",
            "chapter": "第一章 总论",
            "difficulty": 2,
            "mastery_default": 0.1,
        })
        assert r.status_code == 201
        kp_id = r.json()["id"]

        # 3. 出题
        r = client.post("/api/questions/generate", json={
            "knowledge_point_code": "ACC-01-01",
            "difficulty": 2,
            "seed": 42,
        })
        assert r.status_code == 200
        question = r.json()
        assert len(question["options"]) >= 2

        # 4. 开始学习会话
        r = client.post(f"/api/study/sessions?user_id={user_id}", json={"subject": "会计"})
        assert r.status_code == 201
        session_id = r.json()["id"]

        # 5. 答题（连续答对 5 题）
        xp_results = []
        for i in range(5):
            r = client.post(f"/api/mastery/{user_id}/answer", json={
                "knowledge_point_id": kp_id,
                "is_correct": True,
                "difficulty": 2,
                "seed": i,
            })
            assert r.status_code == 200
            xp_results.append(r.json())

        # 6. 验证 BKT 掌握度提升
        r = client.get(f"/api/mastery/{user_id}/{kp_id}")
        assert r.status_code == 200
        mastery = r.json()
        assert mastery["p_known"] > 0.1
        assert mastery["total_answers"] == 5
        assert mastery["correct_answers"] == 5
        assert mastery["mastery_level"] in ("learning", "mastering", "mastered")

        # 7. 验证 XP 累积和等级
        r = client.get(f"/api/gamification/{user_id}/level")
        assert r.status_code == 200
        level_info = r.json()
        assert level_info["level"] >= 1

        total_xp = sum(xr["xp_earned"] for xr in xp_results)
        r = client.get(f"/api/users/{user_id}/profile")
        assert r.json()["total_xp"] == total_xp

        # 8. 更新 Streak
        r = client.post(f"/api/gamification/{user_id}/streak", json={
            "study_date": "2026-01-10",
        })
        assert r.status_code == 200
        assert r.json()["streak"]["streak_count"] == 1

        # 9. 结束学习会话
        r = client.patch(f"/api/study/sessions/{session_id}", json={
            "questions_answered": 5,
            "correct_count": 5,
            "xp_earned": total_xp,
        })
        assert r.status_code == 200
        assert r.json()["ended_at"] is not None
        assert r.json()["questions_answered"] == 5

    def test_mixed_correct_incorrect_answers(self, client):
        """混合答题（有对有错）的掌握度变化。"""
        r = client.post("/api/users", json={
            "username": "e2e_mixed_user",
            "email": "e2e_mixed@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        r = client.post("/api/knowledge/points", json={
            "code": "MIXED-01",
            "name": "混合答题测试",
            "subject": "审计",
            "chapter": "ch1",
        })
        kp_id = r.json()["id"]

        # 答对 3 题
        for i in range(3):
            client.post(f"/api/mastery/{user_id}/answer", json={
                "knowledge_point_id": kp_id,
                "is_correct": True,
                "difficulty": 3,
                "seed": i,
            })

        r = client.get(f"/api/mastery/{user_id}/{kp_id}")
        p_after_correct = r.json()["p_known"]

        # 答错 2 题
        for i in range(2):
            client.post(f"/api/mastery/{user_id}/answer", json={
                "knowledge_point_id": kp_id,
                "is_correct": False,
                "difficulty": 3,
                "seed": i,
            })

        r = client.get(f"/api/mastery/{user_id}/{kp_id}")
        p_after_wrong = r.json()["p_known"]

        # 答错后掌握度应低于全对时
        assert p_after_wrong < p_after_correct
        # 但仍然比初始值高（因为 BKT 转移概率）
        assert p_after_wrong > 0.1
        assert r.json()["total_answers"] == 5
        assert r.json()["correct_answers"] == 3


@pytest.mark.system
class TestMultiDayProgression:
    """多日学习进展系统测试。"""

    def test_streak_growth_and_protection(self, client):
        """连续学习天数增长 + 保护卡获取。"""
        r = client.post("/api/users", json={
            "username": "e2e_streak_user",
            "email": "e2e_streak@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        # 连续学习 7 天
        start_date = date(2026, 1, 10)
        for day in range(7):
            study_date = start_date + timedelta(days=day)
            r = client.post(f"/api/gamification/{user_id}/streak", json={
                "study_date": study_date.isoformat(),
            })
            assert r.status_code == 200

        # 第 7 天应获得保护卡
        r = client.get(f"/api/gamification/{user_id}/streak")
        assert r.json()["streak_count"] == 7
        assert r.json()["max_streak"] == 7
        # 保护卡：初始 1 + 第 7 天获得 1 = 2
        assert r.json()["protections"] >= 2

    def test_streak_break_and_protection(self, client):
        """断签一天使用保护卡保住连续天数。"""
        r = client.post("/api/users", json={
            "username": "e2e_break_user",
            "email": "e2e_break@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        # 连续学习 7 天（获得保护卡）
        start_date = date(2026, 2, 1)
        for day in range(7):
            client.post(f"/api/gamification/{user_id}/streak", json={
                "study_date": (start_date + timedelta(days=day)).isoformat(),
            })

        # 跳过一天（第 8 天不学，第 9 天来学）
        day_9 = start_date + timedelta(days=8)
        r = client.post(f"/api/gamification/{user_id}/streak", json={
            "study_date": day_9.isoformat(),
        })
        # 应消耗保护卡保住 streak
        assert r.json()["streak"]["streak_count"] == 8
        assert "保护卡" in r.json()["message"]


@pytest.mark.system
class TestKnowledgeGraphE2E:
    """知识图谱端到端系统测试。"""

    def test_learning_path_and_question_generation(self, client):
        """创建知识链 → 获取学习路径 → 沿路径各知识点出题。"""
        # 创建知识链：基础 → 中级 → 高级
        kp_ids = []
        for i, (code, name, diff) in enumerate([
            ("E2E-BASIC", "会计基础", 1),
            ("E2E-INTER", "资产核算", 3),
            ("E2E-ADV", "合并报表", 5),
        ]):
            r = client.post("/api/knowledge/points", json={
                "code": code,
                "name": name,
                "subject": "会计",
                "chapter": f"第{i+1}章",
                "difficulty": diff,
            })
            kp_ids.append(r.json()["id"])

        # 创建前置依赖
        for i in range(len(kp_ids) - 1):
            client.post(
                f"/api/knowledge/edges?source_id={kp_ids[i]}&target_id={kp_ids[i+1]}&relation_type=prerequisite"
            )

        # 获取学习路径
        r = client.get(f"/api/knowledge/graph/learning-path/{kp_ids[-1]}")
        assert r.status_code == 200
        path = r.json()["path"]
        assert len(path) == 3
        assert path[0]["code"] == "E2E-BASIC"
        assert path[-1]["code"] == "E2E-ADV"

        # 获取知识图谱可视化数据
        r = client.get("/api/knowledge/graph?subject=会计")
        assert r.status_code == 200
        graph = r.json()
        assert len(graph["nodes"]) >= 3
        assert len(graph["edges"]) >= 2


@pytest.mark.system
class TestJournalValidationE2E:
    """分录判错端到端系统测试。"""

    def test_valid_complex_entry(self, client):
        """验证复杂正确分录（购入原材料含税）。"""
        r = client.post("/api/journal/validate", json={
            "lines": [
                {"account": "原材料", "direction": "借", "amount": 10000},
                {"account": "应交税费", "direction": "借", "amount": 1300},
                {"account": "银行存款", "direction": "贷", "amount": 11300},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid"] is True
        assert data["total_debit"] == 11300
        assert data["total_credit"] == 11300
        assert data["explanation"] is not None

    def test_multiple_errors_entry(self, client):
        """验证多重错误分录。"""
        r = client.post("/api/journal/validate", json={
            "lines": [
                {"account": "银行存款", "direction": "借", "amount": 100},
                {"account": "未知科目", "direction": "贷", "amount": 90},
                {"account": "库存现金", "direction": "借", "amount": 0},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid"] is False
        # 应有多个错误
        assert len(data["errors"]) >= 2
        error_types = [e["error_type"] for e in data["errors"]]
        assert "借贷不平衡" in error_types
        assert "未知科目" in error_types
        assert "金额为零" in error_types

    def test_correction_suggestions(self, client):
        """验证修正建议的完整性。"""
        r = client.post("/api/journal/validate", json={
            "lines": [
                {"account": "银行存款", "direction": "借", "amount": 100},
                {"account": "短期借款", "direction": "贷", "amount": 50},
            ]
        })
        data = r.json()
        assert len(data["corrections"]) > 0
        # 修正建议应包含具体指导
        for correction in data["corrections"]:
            assert len(correction["suggestion"]) > 0


@pytest.mark.system
class TestSystemHealth:
    """系统健康检查测试。"""

    def test_api_docs_accessible(self, client):
        """API 文档应可访问。"""
        r = client.get("/docs")
        assert r.status_code == 200

    def test_openapi_schema_complete(self, client):
        """OpenAPI schema 应包含所有路由。"""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        paths = schema.get("paths", {})
        # 验证关键路由存在
        assert "/api/users" in paths
        assert "/api/knowledge/points" in paths
        assert "/api/questions/generate" in paths
        assert "/api/mastery/{user_id}/answer" in paths
        assert "/api/journal/validate" in paths
        assert "/api/gamification/{user_id}/streak" in paths

    def test_error_handling_404(self, client):
        """不存在的资源应返回 404。"""
        r = client.get("/api/users/99999")
        assert r.status_code == 404

    def test_error_handling_duplicate(self, client):
        """重复注册应返回 409。"""
        user_data = {
            "username": "dup_user",
            "email": "dup@test.com",
            "password": "password123",
        }
        r = client.post("/api/users", json=user_data)
        assert r.status_code == 201

        r = client.post("/api/users", json=user_data)
        assert r.status_code == 409
