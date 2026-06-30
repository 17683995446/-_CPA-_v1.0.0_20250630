"""
应用配置模块。

遵循第一性原理：配置应集中管理、环境可覆盖、默认值合理。
所有引擎和服务的参数在此统一定义，便于后续阶段扩展。
"""
import os
from pathlib import Path


class Settings:
    """全局配置。使用简单对象而非 pydantic-settings 以减少依赖复杂度。"""

    # --- 应用基础 ---
    APP_NAME: str = "CPA Learning App"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # --- 数据库 ---
    # SQLite 文件存放在 backend/data/ 目录下
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DATA_DIR}/cpa_learning.db",
    )

    # --- CPA 考试科目（业务规范）---
    # 注册会计师全国统一考试共 6 科
    CPA_SUBJECTS: list[str] = [
        "会计",      # Accounting
        "审计",      # Auditing
        "财务成本管理",  # Financial Cost Management
        "公司战略与风险管理",  # Strategy & Risk Management
        "经济法",    # Economic Law
        "税法",      # Tax Law
    ]

    # --- FSRS 默认参数（阶段2 使用）---
    FSRS_REQUEST_RETENTION: float = 0.9
    FSRS_MAXIMUM_INTERVAL: int = 36500

    # --- BKT 默认参数（阶段3 使用）---
    BKT_DEFAULT_P_INIT: float = 0.1
    BKT_DEFAULT_P_TRANSIT: float = 0.3
    BKT_DEFAULT_P_GUESS: float = 0.25
    BKT_DEFAULT_P_SLIP: float = 0.1

    # --- 游戏化参数（阶段5 使用）---
    XP_PER_CORRECT: int = 10
    XP_PER_STREAK_DAY: int = 5
    STREAK_PROTECTION_DEFAULT: int = 1

    # --- 题库配置 ---
    QUESTION_BANK_THRESHOLD: int = 5000  # 题库不足此数时触发批量生成
    AUTO_SEED_ON_STARTUP: bool = True    # 启动时是否自动初始化种子数据与题库

    def ensure_dirs(self) -> None:
        """确保运行时目录存在。"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
