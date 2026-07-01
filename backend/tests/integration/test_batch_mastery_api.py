"""
批量掌握度 API 集成测试。

验证规范：
- GET /api/mastery/{user_id}/all 正确响应
- 不存在的用户返回 404
- 答题后掌握度正确更新
- 路由不与 /{user_id}/{kp_id} 冲突
"""
import pytest


@pytest.mark.integration
class TestBatchMasteryAPI:
    """批量掌握度 API 集成测试。"""

    def test_batch_mastery_empty_user(self, client):
        """新用户应返回全部知识点，全部为默认值。"""
        # 注册用户
        r = client.post("/api/users", json={
            "username": "batch_user1",
            "email": "batch1@test.com",
            "password": "password123",
        })
        assert r.status_code == 201
        user_id = r.json()["id"]

        # 创建知识点
        for i in range(3):
            client.post("/api/knowledge/points", json={
                "code": f"BATCH-0{i}-01",
                "name": f"批量测试知识点{i+1}",
                "subject": "会计",
                "chapter": f"第{i+1}章",
                "difficulty": 3,
            })

        # 调用批量掌握度接口
        r = client.get(f"/api/mastery/{user_id}/all")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == user_id
        assert data["total_kps"] == 3
        assert data["answered_kps"] == 0
        assert len(data["items"]) == 3

        for item in data["items"]:
            assert item["total_answers"] == 0
            assert item["mastery_level"] == "unknown"
            assert 0 <= item["p_known"] <= 1

    def test_batch_mastery_after_answer(self, client):
        """答题后批量掌握度应反映更新。"""
        r = client.post("/api/users", json={
            "username": "batch_user2",
            "email": "batch2@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        r = client.post("/api/knowledge/points", json={
            "code": "BATCH-ANS-01",
            "name": "答题测试知识点",
            "subject": "会计",
            "chapter": "第一章",
            "difficulty": 3,
        })
        kp_id = r.json()["id"]

        # 答题
        r = client.post(f"/api/mastery/{user_id}/answer", json={
            "knowledge_point_id": kp_id,
            "is_correct": True,
            "difficulty": 3,
        })
        assert r.status_code == 200

        # 查看批量掌握度
        r = client.get(f"/api/mastery/{user_id}/all")
        assert r.status_code == 200
        data = r.json()
        assert data["answered_kps"] == 1

        answered_item = [i for i in data["items"] if i["total_answers"] > 0][0]
        assert answered_item["total_answers"] == 1
        assert answered_item["correct_answers"] == 1
        assert answered_item["mastery_level"] != "unknown"

    def test_batch_mastery_user_not_found(self, client):
        """不存在的用户应返回 404。"""
        r = client.get("/api/mastery/99999/all")
        assert r.status_code == 404

    def test_route_no_conflict_with_single(self, client):
        """批量路由不与单点路由冲突。"""
        r = client.post("/api/users", json={
            "username": "batch_user3",
            "email": "batch3@test.com",
            "password": "password123",
        })
        user_id = r.json()["id"]

        r = client.post("/api/knowledge/points", json={
            "code": "BATCH-CONF-01",
            "name": "路由冲突测试",
            "subject": "会计",
            "chapter": "第一章",
            "difficulty": 3,
        })
        kp_id = r.json()["id"]

        # 批量接口
        r = client.get(f"/api/mastery/{user_id}/all")
        assert r.status_code == 200

        # 单点接口仍可正常工作
        r = client.get(f"/api/mastery/{user_id}/{kp_id}")
        assert r.status_code == 200
        assert r.json()["knowledge_point_id"] == kp_id
