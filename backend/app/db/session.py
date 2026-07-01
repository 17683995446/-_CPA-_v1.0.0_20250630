"""
数据库会话管理。

遵循依赖注入原则：FastAPI 路由通过 Depends(get_db) 获取会话，
确保每个请求独立会话、自动关闭。
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.base import Base

# SQLite 需要禁用线程检查以支持多线程测试
connect_args = {"check_same_thread": False}
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

# 启用 SQLite 外键约束（默认关闭）
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """创建所有表并执行轻量级列迁移。在应用启动和测试初始化时调用。"""
    # 确保所有模型被导入，以便 Base.metadata 包含全部表定义
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # 轻量级列迁移：为已有数据库添加新列（create_all 不会修改已有表）
    _migrate_columns()


def _migrate_columns() -> None:
    """检查并添加缺失的列到已有表（无需 Alembic 迁移）。"""
    from sqlalchemy import inspect, text as sa_text

    insp = inspect(engine)
    if not insp.has_table("questions"):
        return  # 表不存在，create_all 刚创建，无需迁移

    existing_cols = {col["name"] for col in insp.get_columns("questions")}
    new_cols = ["simple_explanation", "mnemonic", "study_tip"]

    with engine.connect() as conn:
        for col in new_cols:
            if col not in existing_cols:
                conn.execute(sa_text(f"ALTER TABLE questions ADD COLUMN {col} TEXT"))
                print(f"  [migrate] 已添加列: questions.{col}")
        conn.commit()


def drop_db() -> None:
    """删除所有表。用于测试清理。"""
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
