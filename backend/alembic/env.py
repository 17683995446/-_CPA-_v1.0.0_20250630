"""
Alembic 迁移环境配置。

遵循第一性原理：迁移应与 ORM 模型同源，配置应从应用 Settings 读取。
- sqlalchemy.url 从 app.config.settings 动态获取，不依赖 alembic.ini 中的硬编码
- target_metadata 指向 Base.metadata，使 autogenerate 可用
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 确保 app 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# 确保所有模型被导入，以便 Base.metadata 包含全部表定义
import app.models  # noqa: E402, F401

# Alembic 配置
config = context.config

# 从应用 Settings 动态设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标 metadata，用于 autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
