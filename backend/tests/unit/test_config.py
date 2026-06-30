"""
配置系统单元测试。

验证规范：
- Settings 包含所有必要配置项
- 题库阈值可配置
- AUTO_SEED_ON_STARTUP 可切换
- CPA 科目列表完整
"""
from app.config import settings


class TestSettings:
    def test_app_name(self):
        assert settings.APP_NAME is not None
        assert len(settings.APP_NAME) > 0

    def test_database_url(self):
        assert settings.DATABASE_URL is not None
        assert "sqlite" in settings.DATABASE_URL or "postgresql" in settings.DATABASE_URL

    def test_question_bank_threshold(self):
        assert settings.QUESTION_BANK_THRESHOLD > 0
        assert isinstance(settings.QUESTION_BANK_THRESHOLD, int)

    def test_auto_seed_on_startup(self):
        assert isinstance(settings.AUTO_SEED_ON_STARTUP, bool)

    def test_gamification_params(self):
        assert settings.XP_PER_CORRECT > 0
        assert settings.XP_PER_STREAK_DAY > 0
        assert settings.STREAK_PROTECTION_DEFAULT >= 0

    def test_cpa_subjects(self):
        """CPA 六大科目应完整。"""
        expected = {"会计", "审计", "财务成本管理", "公司战略与风险管理", "经济法", "税法"}
        assert expected.issubset(set(settings.CPA_SUBJECTS))

    def test_fsrs_params(self):
        assert 0 < settings.FSRS_REQUEST_RETENTION <= 1
        assert settings.FSRS_MAXIMUM_INTERVAL > 0

    def test_bkt_params(self):
        assert 0 < settings.BKT_DEFAULT_P_INIT < 1
        assert 0 < settings.BKT_DEFAULT_P_TRANSIT < 1
        assert 0 < settings.BKT_DEFAULT_P_GUESS < 0.5
        assert 0 < settings.BKT_DEFAULT_P_SLIP < 0.5
