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
    """创建所有表。在应用启动和测试初始化时调用。"""
    # 确保所有模型被导入，以便 Base.metadata 包含全部表定义
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


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
