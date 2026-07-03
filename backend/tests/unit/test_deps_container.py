"""
依赖注入容器单元测试。

验证规范：
- EngineContainer 正确创建引擎单例
- reset() 清除所有实例
- 线程安全（双重检查锁定）
- get_* 函数返回容器中的引擎
"""
import threading

import pytest

from app.api.deps import (
    EngineContainer,
    get_bkt_engine,
    get_container,
    get_fsrs_engine,
    get_gamification_engine,
    get_journal_validator,
    get_question_generator,
    reset_container,
)
from app.engines.bkt import BKTEngine
from app.engines.fsrs import FSRSEngine
from app.engines.gamification import GamificationEngine
from app.engines.journal_validator import JournalEntryValidator
from app.engines.question_gen import QuestionGenerator


class TestEngineContainer:
    """EngineContainer 核心功能。"""

    def test_creates_fsrs_engine(self):
        container = EngineContainer()
        engine = container.fsrs
        assert isinstance(engine, FSRSEngine)

    def test_creates_bkt_engine(self):
        container = EngineContainer()
        engine = container.bkt
        assert isinstance(engine, BKTEngine)

    def test_creates_question_generator(self):
        container = EngineContainer()
        engine = container.question_generator
        assert isinstance(engine, QuestionGenerator)

    def test_creates_journal_validator(self):
        container = EngineContainer()
        engine = container.journal_validator
        assert isinstance(engine, JournalEntryValidator)

    def test_creates_gamification_engine(self):
        container = EngineContainer()
        engine = container.gamification
        assert isinstance(engine, GamificationEngine)

    def test_singleton_within_container(self):
        """同一容器多次获取应返回同一实例。"""
        container = EngineContainer()
        engine1 = container.fsrs
        engine2 = container.fsrs
        assert engine1 is engine2

    def test_reset_clears_instances(self):
        """reset 后应创建新实例。"""
        container = EngineContainer()
        engine1 = container.fsrs
        container.reset()
        engine2 = container.fsrs
        assert engine1 is not engine2

    def test_reset_clears_all_engines(self):
        """reset 应清除所有引擎。"""
        container = EngineContainer()
        _ = container.fsrs
        _ = container.bkt
        _ = container.gamification
        container.reset()
        # 内部状态应全部为 None
        assert container._fsrs is None
        assert container._bkt is None
        assert container._gamification is None


class TestDependencyFunctions:
    """get_* 依赖函数验证。"""

    def test_get_fsrs_engine_returns_container_instance(self):
        reset_container()
        engine = get_fsrs_engine()
        assert isinstance(engine, FSRSEngine)

    def test_get_bkt_engine_returns_container_instance(self):
        reset_container()
        engine = get_bkt_engine()
        assert isinstance(engine, BKTEngine)

    def test_get_gamification_engine_returns_container_instance(self):
        reset_container()
        engine = get_gamification_engine()
        assert isinstance(engine, GamificationEngine)

    def test_get_question_generator_returns_container_instance(self):
        reset_container()
        engine = get_question_generator()
        assert isinstance(engine, QuestionGenerator)

    def test_get_journal_validator_returns_container_instance(self):
        reset_container()
        engine = get_journal_validator()
        assert isinstance(engine, JournalEntryValidator)

    def test_get_container_returns_same_instance(self):
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2

    def test_reset_container_works(self):
        engine1 = get_fsrs_engine()
        reset_container()
        engine2 = get_fsrs_engine()
        assert engine1 is not engine2


class TestThreadSafety:
    """线程安全验证。"""

    def test_concurrent_initialization(self):
        """多线程同时获取引擎应只创建一个实例。"""
        container = EngineContainer()
        results: list[FSRSEngine] = []

        def get_engine():
            results.append(container.fsrs)

        threads = [threading.Thread(target=get_engine) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有线程应获得同一实例
        assert len(results) == 10
        assert all(r is results[0] for r in results)
