"""
CPA 题库数据包。

公开接口（仅以下两个函数供外部调用，来自 main.py）：
- generate_mass_questions(db) -> int
- fix_existing_database(db) -> dict

旧入口 app.mass_questions 已重构为本包，并通过 deprecation shim 保持向后兼容。
"""
from app.question_data.fixes import fix_existing_database
from app.question_data.orchestrator import generate_mass_questions

__all__ = ["generate_mass_questions", "fix_existing_database"]
