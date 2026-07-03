"""
应用配置模块。

遵循第一性原理：配置应集中管理、环境可覆盖、默认值合理、启动时校验。
所有引擎和服务的参数在此统一定义，消除配置双源问题。

环境分层：
- development: DEBUG=True, AUTO_SEED=True, SQLite 内存/文件
- testing: AUTO_SEED=False, SQLite 内存
- production: DEBUG=False, AUTO_SEED=False, PostgreSQL

环境变量通过 _get_env() 统一读取并做类型转换，避免散落的 os.getenv 调用。
"""
import os
from enum import Enum
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


class Environment(str, Enum):
    """运行环境枚举。"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


def _get_env(key: str, default: T, cast: type = str) -> T:
    """从环境变量读取并做类型转换。

    统一处理 bool/int/float/str 四种类型，避免各处重复 lower()==\"true\" 模式。
    """
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    if cast is bool:
        return raw.lower() in ("true", "1", "yes", "on")  # type: ignore
    if cast is int:
        return int(raw)  # type: ignore
    if cast is float:
        return float(raw)  # type: ignore
    return raw  # type: ignore


class Settings:
    """全局配置。

    使用简单对象而非 pydantic-settings 以减少依赖复杂度。
    所有参数支持环境变量覆盖，启动时通过 validate() 校验合法性。
    """

    def __init__(self) -> None:
        # --- 环境检测 ---
        env_str = _get_env("APP_ENV", "development", str)
        self.ENVIRONMENT = Environment(env_str) if env_str in [e.value for e in Environment] else Environment.DEVELOPMENT
        self.DEBUG: bool = _get_env("DEBUG", self.ENVIRONMENT == Environment.DEVELOPMENT, bool)

        # --- 应用基础 ---
        self.APP_NAME: str = "CPA Learning App"
        self.APP_VERSION: str = "0.2.0"
        self.API_PREFIX: str = _get_env("API_PREFIX", "/api", str)

        # --- 数据库 ---
        self.BASE_DIR: Path = Path(__file__).resolve().parent.parent
        self.DATA_DIR: Path = Path(_get_env("DATA_DIR", str(self.BASE_DIR / "data"), str))
        self.DATABASE_URL: str = _get_env(
            "DATABASE_URL",
            f"sqlite:///{self.DATA_DIR}/cpa_learning.db",
        )

        # --- CPA 考试科目（业务规范）---
        # 注册会计师全国统一考试共 6 科
        self.CPA_SUBJECTS: list[str] = [
            "会计",
            "审计",
            "财务成本管理",
            "公司战略与风险管理",
            "经济法",
            "税法",
        ]

        # --- FSRS 间隔重复参数 ---
        self.FSRS_REQUEST_RETENTION: float = _get_env("FSRS_REQUEST_RETENTION", 0.9, float)
        self.FSRS_MAXIMUM_INTERVAL: int = _get_env("FSRS_MAXIMUM_INTERVAL", 36500, int)

        # --- BKT 知识追踪参数 ---
        self.BKT_DEFAULT_P_INIT: float = _get_env("BKT_DEFAULT_P_INIT", 0.1, float)
        self.BKT_DEFAULT_P_TRANSIT: float = _get_env("BKT_DEFAULT_P_TRANSIT", 0.3, float)
        self.BKT_DEFAULT_P_GUESS: float = _get_env("BKT_DEFAULT_P_GUESS", 0.25, float)
        self.BKT_DEFAULT_P_SLIP: float = _get_env("BKT_DEFAULT_P_SLIP", 0.1, float)

        # --- BKT 掌握度阈值 ---
        self.BKT_MASTERY_UNKNOWN: float = 0.3
        self.BKT_MASTERY_LEARNING: float = 0.7
        self.BKT_MASTERY_MASTERING: float = 0.95
        self.BKT_MASTERY_MASTERED: float = 0.95

        # --- 游戏化参数 ---
        self.XP_PER_CORRECT: int = _get_env("XP_PER_CORRECT", 10, int)
        self.XP_PER_STREAK_DAY: int = _get_env("XP_PER_STREAK_DAY", 5, int)
        self.STREAK_PROTECTION_DEFAULT: int = _get_env("STREAK_PROTECTION_DEFAULT", 1, int)
        self.GAMIFICATION_CRITICAL_CHANCE: float = _get_env("GAMIFICATION_CRITICAL_CHANCE", 0.1, float)
        self.GAMIFICATION_CRITICAL_MULTIPLIER: float = _get_env("GAMIFICATION_CRITICAL_MULTIPLIER", 3.0, float)
        self.GAMIFICATION_BASE_LEVEL_XP: int = _get_env("GAMIFICATION_BASE_LEVEL_XP", 100, int)
        self.GAMIFICATION_LEVEL_GROWTH_RATE: float = _get_env("GAMIFICATION_LEVEL_GROWTH_RATE", 1.5, float)
        self.GAMIFICATION_STREAK_PROTECTION_MAX: int = _get_env("GAMIFICATION_STREAK_PROTECTION_MAX", 3, int)
        self.GAMIFICATION_STREAK_BONUS_THRESHOLD: int = _get_env("GAMIFICATION_STREAK_BONUS_THRESHOLD", 7, int)

        # --- 题库配置 ---
        self.QUESTION_BANK_THRESHOLD: int = _get_env("QUESTION_BANK_THRESHOLD", 5000, int)
        self.AUTO_SEED_ON_STARTUP: bool = _get_env(
            "AUTO_SEED_ON_STARTUP",
            self.ENVIRONMENT != Environment.TESTING,
            bool,
        )
        self.QUESTION_DB_VERSION: str = "2026-07-02-v5"

        # --- LLM 配置 ---
        # 使用 OpenAI 兼容接口，支持 DeepSeek / Qwen / OpenAI 等
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-14B-Instruct")
        self.LLM_EMBEDDING_MODEL: str = os.getenv("LLM_EMBEDDING_MODEL", "BAAI/bge-m3")
        self.LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
        self.LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        self.LLM_EMBEDDING_DIM: int = int(os.getenv("LLM_EMBEDDING_DIM", "1024"))
        self.LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"

        # --- 日志配置 ---
        self.LOG_LEVEL: str = _get_env("LOG_LEVEL", "DEBUG" if self.DEBUG else "INFO", str)

    def ensure_dirs(self) -> None:
        """确保运行时目录存在。"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """校验配置合法性，返回错误消息列表（空列表表示全部通过）。

        启动时调用以提前发现配置错误，避免运行时崩溃。
        """
        errors: list[str] = []

        # 概率参数必须在 (0, 1) 区间
        for name, val in [
            ("FSRS_REQUEST_RETENTION", self.FSRS_REQUEST_RETENTION),
            ("BKT_DEFAULT_P_INIT", self.BKT_DEFAULT_P_INIT),
            ("BKT_DEFAULT_P_TRANSIT", self.BKT_DEFAULT_P_TRANSIT),
        ]:
            if not 0 < val < 1:
                errors.append(f"{name} 必须在 (0, 1) 区间，当前值: {val}")

        # guess 和 slip 应小于 0.5（否则题目信息量为负）
        for name, val in [
            ("BKT_DEFAULT_P_GUESS", self.BKT_DEFAULT_P_GUESS),
            ("BKT_DEFAULT_P_SLIP", self.BKT_DEFAULT_P_SLIP),
        ]:
            if not 0 < val < 0.5:
                errors.append(f"{name} 必须在 (0, 0.5) 区间，当前值: {val}")

        # 掌握度阈值应递增
        if not (self.BKT_MASTERY_UNKNOWN < self.BKT_MASTERY_LEARNING < self.BKT_MASTERY_MASTERED):
            errors.append("BKT 掌握度阈值应递增: UNKNOWN < LEARNING < MASTERED")

        # 正整数约束
        for name, val in [
            ("XP_PER_CORRECT", self.XP_PER_CORRECT),
            ("QUESTION_BANK_THRESHOLD", self.QUESTION_BANK_THRESHOLD),
            ("FSRS_MAXIMUM_INTERVAL", self.FSRS_MAXIMUM_INTERVAL),
        ]:
            if val <= 0:
                errors.append(f"{name} 必须为正整数，当前值: {val}")

        # 临界概率应在 [0, 1) 区间
        if not 0 <= self.GAMIFICATION_CRITICAL_CHANCE < 1:
            errors.append(f"GAMIFICATION_CRITICAL_CHANCE 必须在 [0, 1) 区间，当前值: {self.GAMIFICATION_CRITICAL_CHANCE}")

        return errors

    @property
    def is_production(self) -> bool:
        """是否为生产环境。"""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        """是否为测试环境。"""
        return self.ENVIRONMENT == Environment.TESTING


settings = Settings()
settings.ensure_dirs()
