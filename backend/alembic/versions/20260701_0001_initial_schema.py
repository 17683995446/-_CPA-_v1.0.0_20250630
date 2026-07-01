"""initial schema with question explanation modules

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-01 00:00:00

本迁移创建初始表结构并添加题目解析四模块字段。
替代 db/session.py 中手写的 ALTER TABLE 迁移逻辑。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    初始迁移：确保 questions 表包含解析四模块字段。

    对于已存在 questions 表的数据库（create_all 已建表），
    此迁移安全地添加缺失的列，效果等同于原 _migrate_columns()。
    对于全新数据库，create_all 已创建完整表结构，此迁移为空操作。
    """
    # 检查 questions 表是否存在
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("questions"):
        # 全新数据库，表尚未创建（将由 create_all 创建完整结构）
        return

    existing_cols = {col["name"] for col in inspector.get_columns("questions")}
    new_cols = [
        ("simple_explanation", sa.Text()),
        ("mnemonic", sa.Text()),
        ("study_tip", sa.Text()),
    ]

    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            op.add_column("questions", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    """回滚：移除解析四模块字段。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("questions"):
        return

    existing_cols = {col["name"] for col in inspector.get_columns("questions")}

    for col_name in ["study_tip", "mnemonic", "simple_explanation"]:
        if col_name in existing_cols:
            op.drop_column("questions", col_name)
