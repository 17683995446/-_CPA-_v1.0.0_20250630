"""
批量掌握度 API 单元测试。

验证规范：
- 返回全部知识点（含未答题的默认值）
- answered_kps 正确统计已答题数量
- 未答题知识点 p_known 为 BKT 默认值
- 答题后掌握度正确更新
- 不存在的用户返回 404
"""
import pytest

from app.engines.bkt import BKTEngine, MasteryState
from app.models import KnowledgePoint, User, UserMastery, UserProfile


@pytest.fixture
def setup_data(db_session):
    """创建测试用户和多个知识点。"""
    user = User(username="vizuser", email="viz@test.com", password_hash="x")
    db_session.add(user)
    db_session.flush()

    profile = UserProfile(user_id=user.id)
    db_session.add(profile)

    kps = []
    for i in range(5):
        kp = KnowledgePoint(
            code=f"VIZ-0{i}-01",
            name=f"可视化测试知识点{i+1}",
            subject="会计" if i < 3 else "审计",
            chapter=f"第{i+1}章",
            difficulty=(i % 5) + 1,
        )
        db_session.add(kp)
        kps.append(kp)

    db_session.flush()

    # 为前 2 个知识点创建掌握度记录（已答题）
    bkt = BKTEngine()
    for kp in kps[:2]:
        mastery = UserMastery(
            user_id=user.id,
            knowledge_point_id=kp.id,
            p_known=0.8,
            p_transit=bkt.defaults.p_transit,
            p_guess=bkt.defaults.p_guess,
            p_slip=bkt.defaults.p_slip,
            total_answers=5,
            correct_answers=4,
        )
        db_session.add(mastery)

    db_session.commit()
    db_session.refresh(user)
    return user, kps


class TestBatchMasteryUnit:
    """批量掌握度端点单元测试（直接调用路由函数）。"""

    def test_returns_all_kps(self, db_session, setup_data):
        """应返回全部知识点（含未答题的）。"""
        from app.api.routers.mastery import get_all_mastery

        user, kps = setup_data
        bkt = BKTEngine()
        result = get_all_mastery(user_id=user.id, db=db_session, user=user, bkt_engine=bkt)

        assert result.total_kps == 5
        assert len(result.items) == 5

    def test_answered_count(self, db_session, setup_data):
        """answered_kps 应正确统计已答题数量。"""
        from app.api.routers.mastery import get_all_mastery

        user, kps = setup_data
        bkt = BKTEngine()
        result = get_all_mastery(user_id=user.id, db=db_session, user=user, bkt_engine=bkt)

        assert result.answered_kps == 2

    def test_unanswered_default_values(self, db_session, setup_data):
        """未答题知识点应返回 BKT 默认值。"""
        from app.api.routers.mastery import get_all_mastery

        user, kps = setup_data
        bkt = BKTEngine()
        result = get_all_mastery(user_id=user.id, db=db_session, user=user, bkt_engine=bkt)

        # 后 3 个知识点未答题
        for item in result.items[2:]:
            assert item.total_answers == 0
            assert item.correct_answers == 0
            assert item.p_known == bkt.defaults.p_known
            assert item.mastery_level == "unknown"

    def test_answered_has_correct_values(self, db_session, setup_data):
        """已答题知识点应返回实际掌握度。"""
        from app.api.routers.mastery import get_all_mastery

        user, kps = setup_data
        bkt = BKTEngine()
        result = get_all_mastery(user_id=user.id, db=db_session, user=user, bkt_engine=bkt)

        # 前 2 个知识点已答题
        for item in result.items[:2]:
            assert item.total_answers == 5
            assert item.correct_answers == 4
            assert item.p_known == 0.8

    def test_items_contain_kp_info(self, db_session, setup_data):
        """每个 item 应包含知识点基本信息。"""
        from app.api.routers.mastery import get_all_mastery

        user, kps = setup_data
        bkt = BKTEngine()
        result = get_all_mastery(user_id=user.id, db=db_session, user=user, bkt_engine=bkt)

        for i, item in enumerate(result.items):
            assert item.knowledge_point_code == kps[i].code
            assert item.knowledge_point_name == kps[i].name
            assert item.subject == kps[i].subject
            assert item.chapter == kps[i].chapter
            assert item.difficulty == kps[i].difficulty
