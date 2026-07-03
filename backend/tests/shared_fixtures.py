"""
共享测试 Fixtures。

提供跨测试文件复用的 fixture，减少 conftest.py 膨胀。
使用方式：在测试文件中通过 pytest fixture 引用。

    @pytest.fixture
    def setup(self, db_session):
        from tests.factories import make_full_setup
        return make_full_setup(db_session)
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from tests.factories import make_full_setup, make_user, make_kp


@pytest.fixture
def isolated_db():
    """提供完全隔离的内存数据库会话。

    每个测试函数获得独立的 SQLite 实例，互不干扰。
    适用于不需要 FastAPI TestClient 的纯数据层测试。
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def setup_with_data(isolated_db):
    """提供预填充的测试数据集。

    包含：1个用户 + 1个知识点 + 5道题（含选项）+ 1条掌握度 + 1个用户画像。
    """
    data = make_full_setup(isolated_db, question_count=5)
    isolated_db.commit()
    return data


@pytest.fixture
def setup_user_only(isolated_db):
    """仅提供单个用户。"""
    user = make_user(isolated_db, username="fixture_user", email="fixture@test.com")
    isolated_db.commit()
    return user


@pytest.fixture
def setup_kp_only(isolated_db):
    """仅提供单个知识点。"""
    kp = make_kp(isolated_db)
    isolated_db.commit()
    return kp


@pytest.fixture
def clean_container():
    """重置引擎容器，确保测试间引擎状态隔离。"""
    from app.api.deps import reset_container
    reset_container()
    yield
    reset_container()
