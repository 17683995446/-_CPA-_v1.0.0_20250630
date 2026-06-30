"""
阶段7 API 集成测试：验证各 API 路由间的协作。

测试跨路由场景：
1. 用户注册 → 知识点创建 → 出题 → 答题 → BKT/FSRS/XP 更新
2. 知识点 → 知识图谱 → 学习路径
3. FSRS 复习卡片创建 → 获取到期卡片 → 提交评分
4. 游戏化：Streak 更新 → 等级查询 → 成就检查
5. 分录验证：正确/错误分录
6. 学习会话生命周期
"""
import pytest


@pytest.mark.integration
class TestUserKnowledgeFlow:
    """用户 + 知识点 + 出题 + 答题 集成流程。"""

    def test_register_and_create_kp(self, client):
        """注册用户 → 创建知识点 → 查询验证。"""
        # 1. 注册用户
        r = client.post("/api/users", json={
            "username": "int_api_user1",
            "email": "int_api1@test.com",
            "password": "password123",
        })
        assert r.status_code == 201
        user_id = r.json()["id"]

        # 2. 创建知识点
        r = client.post("/api/knowledge/points", json={
            "code": "API-INT-01",
            "name": "API集成测试知识点",
            "subject": "会计",
            "chapter": "第一章",
            "difficulty": 3,
        })
        assert r.status_code == 201
        kp_id = r.json()["id"]

        # 3. 查询知识点
        r = client.get(f"/api/knowledge/points/{kp_id}")
        assert r.status_code == 200
        assert r.json()["code"] == "API-INT-01"

        # 4. 获取用户画像
        r = client.get(f"/api/users/{user_id}/profile")
        assert r.status_code == 200
        assert r.json()["total_xp"] == 0
        assert r.json()["current_level"] == 1

    def test_generate_question_and_answer(self, client):
        """出题 → 答题 → 验证 BKT/FSRS/XP 更新。"""
        # 准备用户和知识点
        r = client.post("/api/users", json={
            "username": "int_api_user2",
            "email": "int_api2@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        r = client.post("/api/knowledge/points", json={
            "code": "ACC-01-01",
            "name": "借贷记账法基础",
            "subject": "会计",
            "chapter": "第一章",
            "difficulty": 2,
        })
        kp_id = r.json()["id"]

        # 出题（使用默认模板）
        r = client.post("/api/questions/generate", json={
            "knowledge_point_code": "ACC-01-01",
            "difficulty": 2,
            "seed": 42,
        })
        assert r.status_code == 200
        question = r.json()
        assert "万元" in question["content"]
        assert len(question["options"]) >= 2

        # 答题（答对）
        r = client.post(f"/api/mastery/{user_id}/answer", json={
            "knowledge_point_id": kp_id,
            "is_correct": True,
            "difficulty": 2,
            "seed": 42,
        })
        assert r.status_code == 200
        result = r.json()
        assert result["p_known_after"] > result["p_known_before"]
        assert result["xp_earned"] > 0
        assert result["mastery_level"] in ("learning", "mastering", "mastered")

    def test_answer_wrong_decreases_mastery(self, client):
        """答错后掌握度应下降。"""
        r = client.post("/api/users", json={
            "username": "int_api_user3",
            "email": "int_api3@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        r = client.post("/api/knowledge/points", json={
            "code": "API-INT-03",
            "name": "测试知识点3",
            "subject": "会计",
            "chapter": "ch1",
            "difficulty": 3,
        })
        kp_id = r.json()["id"]

        # 先答对建立掌握度
        client.post(f"/api/mastery/{user_id}/answer", json={
            "knowledge_point_id": kp_id,
            "is_correct": True,
            "difficulty": 3,
            "seed": 42,
        })

        # 查看掌握度
        r = client.get(f"/api/mastery/{user_id}/{kp_id}")
        p_after_correct = r.json()["p_known"]

        # 答错
        r = client.post(f"/api/mastery/{user_id}/answer", json={
            "knowledge_point_id": kp_id,
            "is_correct": False,
            "difficulty": 3,
            "seed": 42,
        })
        p_after_wrong = r.json()["p_known_after"]

        assert p_after_wrong < p_after_correct


@pytest.mark.integration
class TestReviewFlow:
    """FSRS 间隔重复 API 集成。"""

    def test_review_with_existing_card(self, client, db_session):
        """使用 db_session 准备数据，通过 API 提交复习。"""
        from app.models import KnowledgePoint, Question, ReviewCard, User
        from datetime import date

        user = User(username="rev_api_user", email="rev_api@test.com", password_hash="h")
        kp = KnowledgePoint(code="REV-API-01", name="复习API", subject="会计", chapter="ch1")
        db_session.add_all([user, kp])
        db_session.flush()
        q = Question(knowledge_point_id=kp.id, question_type="single_choice",
                     content="测试题", answer="A")
        db_session.add(q)
        db_session.flush()

        card = ReviewCard(
            user_id=user.id, question_id=q.id, knowledge_point_id=kp.id,
            due=date(2026, 1, 10),
        )
        db_session.add(card)
        db_session.commit()

        # 获取到期卡片
        r = client.get(f"/api/review/{user.id}/due?target_date=2026-01-15")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

        # 提交评分（Good=3）
        r = client.post(f"/api/review/{user.id}/cards/{card.id}", json={"rating": 3})
        assert r.status_code == 200
        result = r.json()
        assert result["stability_after"] > 0
        assert result["state"] == "review"


@pytest.mark.integration
class TestGamificationFlow:
    """游戏化 API 集成。"""

    def test_streak_update_and_level(self, client):
        """Streak 更新 → 等级查询。"""
        r = client.post("/api/users", json={
            "username": "game_user",
            "email": "game@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        # 首次更新 streak
        r = client.post(f"/api/gamification/{user_id}/streak", json={
            "study_date": "2026-01-10",
        })
        assert r.status_code == 200
        assert r.json()["streak"]["streak_count"] == 1

        # 连续第二天
        r = client.post(f"/api/gamification/{user_id}/streak", json={
            "study_date": "2026-01-11",
        })
        assert r.json()["streak"]["streak_count"] == 2

        # 查询等级
        r = client.get(f"/api/gamification/{user_id}/level")
        assert r.status_code == 200
        assert r.json()["level"] >= 1

    def test_xp_accumulation_and_level_up(self, client):
        """答题积累 XP → 等级提升。"""
        r = client.post("/api/users", json={
            "username": "xp_user",
            "email": "xp@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        r = client.post("/api/knowledge/points", json={
            "code": "XP-01",
            "name": "XP测试",
            "subject": "会计",
            "chapter": "ch1",
        })
        kp_id = r.json()["id"]

        # 答对 10 道题积累 XP
        total_xp = 0
        for i in range(10):
            r = client.post(f"/api/mastery/{user_id}/answer", json={
                "knowledge_point_id": kp_id,
                "is_correct": True,
                "difficulty": 3,
                "seed": i,
            })
            total_xp = r.json()["total_xp"]

        assert total_xp > 0

        # 查询等级
        r = client.get(f"/api/gamification/{user_id}/level")
        assert r.status_code == 200
        assert r.json()["level"] >= 1


@pytest.mark.integration
class TestJournalFlow:
    """分录判错 API 集成。"""

    def test_validate_correct_entry(self, client):
        """验证正确分录。"""
        r = client.post("/api/journal/validate", json={
            "lines": [
                {"account": "银行存款", "direction": "借", "amount": 100},
                {"account": "短期借款", "direction": "贷", "amount": 100},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid"] is True
        assert data["total_debit"] == 100
        assert data["total_credit"] == 100
        assert data["balance_diff"] == 0

    def test_validate_unbalanced_entry(self, client):
        """验证不平衡分录。"""
        r = client.post("/api/journal/validate", json={
            "lines": [
                {"account": "银行存款", "direction": "借", "amount": 100},
                {"account": "短期借款", "direction": "贷", "amount": 90},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0
        assert any(e["error_type"] == "借贷不平衡" for e in data["errors"])

    def test_validate_with_corrections(self, client):
        """验证错误分录并获取修正建议。"""
        r = client.post("/api/journal/validate", json={
            "lines": [
                {"account": "银行存款", "direction": "借", "amount": 100},
                {"account": "短期借款", "direction": "贷", "amount": 90},
            ]
        })
        data = r.json()
        assert len(data["corrections"]) > 0

    def test_list_accounts(self, client):
        """获取标准科目表。"""
        r = client.get("/api/journal/accounts")
        assert r.status_code == 200
        accounts = r.json()
        assert "银行存款" in accounts
        assert "短期借款" in accounts
        assert accounts["银行存款"] == "资产"


@pytest.mark.integration
class TestStudySessionFlow:
    """学习会话 API 集成。"""

    def test_session_lifecycle(self, client):
        """学习会话完整生命周期。"""
        r = client.post("/api/users", json={
            "username": "session_user",
            "email": "session@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        # 开始会话
        r = client.post(f"/api/study/sessions?user_id={user_id}", json={
            "subject": "会计",
        })
        assert r.status_code == 201
        session_id = r.json()["id"]
        assert r.json()["ended_at"] is None

        # 结束会话（更新统计）
        r = client.patch(f"/api/study/sessions/{session_id}", json={
            "questions_answered": 10,
            "correct_count": 7,
            "xp_earned": 80,
        })
        assert r.status_code == 200
        assert r.json()["ended_at"] is not None
        assert r.json()["questions_answered"] == 10
        assert r.json()["correct_count"] == 7
        assert r.json()["xp_earned"] == 80

    def test_list_sessions(self, client):
        """查询用户学习会话历史。"""
        r = client.post("/api/users", json={
            "username": "session_list_user",
            "email": "session_list@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        # 创建多个会话
        for _ in range(3):
            client.post(f"/api/study/sessions?user_id={user_id}", json={"subject": "会计"})

        r = client.get(f"/api/study/{user_id}/sessions")
        assert r.status_code == 200
        assert len(r.json()) == 3


@pytest.mark.integration
class TestKnowledgeGraphFlow:
    """知识图谱 API 集成。"""

    def test_graph_and_learning_path(self, client):
        """创建知识点和边 → 获取图谱 → 获取学习路径。"""
        # 创建 3 个知识点
        kp_ids = []
        for i, code in enumerate(["GRAPH-01", "GRAPH-02", "GRAPH-03"]):
            r = client.post("/api/knowledge/points", json={
                "code": code,
                "name": f"图谱知识点{i+1}",
                "subject": "会计",
                "chapter": f"ch{i+1}",
                "difficulty": i + 1,
            })
            kp_ids.append(r.json()["id"])

        # 创建前置依赖边
        client.post(
            f"/api/knowledge/edges?source_id={kp_ids[0]}&target_id={kp_ids[1]}&relation_type=prerequisite"
        )
        client.post(
            f"/api/knowledge/edges?source_id={kp_ids[1]}&target_id={kp_ids[2]}&relation_type=prerequisite"
        )

        # 获取知识图谱
        r = client.get("/api/knowledge/graph?subject=会计")
        assert r.status_code == 200
        graph = r.json()
        assert len(graph["nodes"]) >= 3
        assert len(graph["edges"]) >= 2

        # 获取学习路径
        r = client.get(f"/api/knowledge/graph/learning-path/{kp_ids[2]}")
        assert r.status_code == 200
        path = r.json()
        assert len(path["path"]) == 3
        assert path["path"][0]["code"] == "GRAPH-01"
        assert path["path"][-1]["code"] == "GRAPH-03"
