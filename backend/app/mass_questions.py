"""
[已废弃] CPA 大规模题库生成器。

此模块已重构为 `app.question_data` 包，请直接导入：
    from app.question_data import generate_mass_questions

本文件仅保留向后兼容的重新导出，将在未来版本中移除。
"""
import warnings

from app.question_data.orchestrator import generate_mass_questions
from app.question_data.fixes import fix_existing_database

# 发出弃用警告
warnings.warn(
    "app.mass_questions 已弃用，请使用 app.question_data 包。",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["generate_mass_questions", "fix_existing_database"]
