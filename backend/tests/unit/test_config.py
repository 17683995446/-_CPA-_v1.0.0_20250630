"""
配置系统单元测试。

验证规范：
- Settings 包含所有必要配置项
- 题库阈值可配置
- AUTO_SEED_ON_STARTUP 可切换
- CPA 科目列表完整
- 环境检测正确
- validate() 能发现非法配置
"""
import os

import pytest

from app.config import Environment, Settings, _get_env


class TestSettings:
    """基础配置项验证。"""

    def test_app_name(self):
        from app.config import settings

        assert settings.APP_NAME is not None
        assert len(settings.APP_NAME) > 0

    def test_database_url(self):
        from app.config import settings

        assert settings.DATABASE_URL is not None
        assert "sqlite" in settings.DATABASE_URL or "postgresql" in settings.DATABASE_URL

    def test_question_bank_threshold(self):
        from app.config import settings

        assert settings.QUESTION_BANK_THRESHOLD > 0
        assert isinstance(settings.QUESTION_BANK_THRESHOLD, int)

    def test_auto_seed_on_startup(self):
        from app.config import settings

        assert isinstance(settings.AUTO_SEED_ON_STARTUP, bool)

    def test_gamification_params(self):
        from app.config import settings

        assert settings.XP_PER_CORRECT > 0
        assert settings.XP_PER_STREAK_DAY > 0
        assert settings.STREAK_PROTECTION_DEFAULT >= 0

    def test_cpa_subjects(self):
        """CPA 六大科目应完整。"""
        from app.config import settings

        expected = {"会计", "审计", "财务成本管理", "公司战略与风险管理", "经济法", "税法"}
        assert expected.issubset(set(settings.CPA_SUBJECTS))

    def test_fsrs_params(self):
        from app.config import settings

        assert 0 < settings.FSRS_REQUEST_RETENTION <= 1
        assert settings.FSRS_MAXIMUM_INTERVAL > 0

    def test_bkt_params(self):
        from app.config import settings

        assert 0 < settings.BKT_DEFAULT_P_INIT < 1
        assert 0 < settings.BKT_DEFAULT_P_TRANSIT < 1
        assert 0 < settings.BKT_DEFAULT_P_GUESS < 0.5
        assert 0 < settings.BKT_DEFAULT_P_SLIP < 0.5

    def test_app_version_updated(self):
        """APP_VERSION 应与 pyproject.toml 一致。"""
        from app.config import settings

        assert settings.APP_VERSION == "0.2.0"

    def test_api_prefix_exists(self):
        """API_PREFIX 应存在且以 / 开头。"""
        from app.config import settings

        assert settings.API_PREFIX.startswith("/")


class TestEnvironmentDetection:
    """环境检测验证。"""

    def test_environment_enum_values(self):
        assert Environment.DEVELOPMENT == "development"
        assert Environment.TESTING == "testing"
        assert Environment.PRODUCTION == "production"

    def test_default_environment_is_development(self):
        s = Settings()
        assert s.ENVIRONMENT == Environment.DEVELOPMENT

    def test_is_production_property(self):
        s = Settings()
        assert s.is_production is False

    def test_is_testing_property(self):
        s = Settings()
        assert s.is_testing is False


class TestEnvParsing:
    """环境变量解析验证。"""

    def test_get_env_bool_true(self):
        os.environ["TEST_BOOL"] = "true"
        assert _get_env("TEST_BOOL", False, bool) is True
        del os.environ["TEST_BOOL"]

    def test_get_env_bool_false(self):
        os.environ["TEST_BOOL"] = "false"
        assert _get_env("TEST_BOOL", True, bool) is False
        del os.environ["TEST_BOOL"]

    def test_get_env_int(self):
        os.environ["TEST_INT"] = "42"
        assert _get_env("TEST_INT", 0, int) == 42
        del os.environ["TEST_INT"]

    def test_get_env_float(self):
        os.environ["TEST_FLOAT"] = "3.14"
        assert _get_env("TEST_FLOAT", 0.0, float) == 3.14
        del os.environ["TEST_FLOAT"]

    def test_get_env_default_when_unset(self):
        assert _get_env("NONEXISTENT_KEY", "default", str) == "default"

    def test_get_env_default_when_empty(self):
        os.environ["TEST_EMPTY"] = ""
        assert _get_env("TEST_EMPTY", "fallback", str) == "fallback"
        del os.environ["TEST_EMPTY"]


class TestValidation:
    """validate() 方法验证。"""

    def test_default_config_passes_validation(self):
        s = Settings()
        errors = s.validate()
        assert errors == [], f"默认配置应通过校验，但发现错误: {errors}"

    def test_invalid_probability_detected(self):
        s = Settings()
        s.FSRS_REQUEST_RETENTION = 1.5
        errors = s.validate()
        assert any("FSRS_REQUEST_RETENTION" in e for e in errors)

    def test_invalid_guess_detected(self):
        s = Settings()
        s.BKT_DEFAULT_P_GUESS = 0.6
        errors = s.validate()
        assert any("BKT_DEFAULT_P_GUESS" in e for e in errors)

    def test_non_positive_xp_detected(self):
        s = Settings()
        s.XP_PER_CORRECT = -5
        errors = s.validate()
        assert any("XP_PER_CORRECT" in e for e in errors)

    def test_invalid_critical_chance_detected(self):
        s = Settings()
        s.GAMIFICATION_CRITICAL_CHANCE = 1.5
        errors = s.validate()
        assert any("GAMIFICATION_CRITICAL_CHANCE" in e for e in errors)
