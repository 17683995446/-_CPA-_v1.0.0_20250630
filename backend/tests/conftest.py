"""
测试配置模块。

架构规范：
- 每个测试使用独立的内存 SQLite 数据库，互不干扰
- 提供 db_session fixture 和 test_app fixture
- 数据库在每次测试前后自动创建和清理
- 通过关闭 AUTO_SEED_ON_STARTUP 避免测试时触发种子数据与题库生成
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# 测试前关闭自动种子，避免 lifespan 污染真实数据库
settings.AUTO_SEED_ON_STARTUP = False


@pytest.fixture
def db_engine():
    """创建内存数据库引擎，测试结束自动销毁。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # 确保所有模型被导入
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """提供数据库会话，测试结束自动回滚。"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """提供 FastAPI 测试客户端，注入测试数据库会话。"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
