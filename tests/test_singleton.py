"""Singleton pattern: one Settings object and one database engine."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.patterns.singleton import SingletonMeta


def test_settings_is_a_single_instance():
    assert Settings() is Settings()


def test_database_manager_shares_one_engine():
    assert DatabaseManager() is DatabaseManager()
    assert DatabaseManager().engine is DatabaseManager().engine


def test_each_session_is_separate():
    manager = DatabaseManager()
    with manager.new_session() as first, manager.new_session() as second:
        assert first is not second
        assert first.get_bind() is second.get_bind()


def test_only_one_instance_is_created_across_threads():
    thread_count = 16
    barrier = Barrier(thread_count)
    created = []

    class Resource(metaclass=SingletonMeta):
        def __init__(self):
            created.append(self)

    def build(_):
        barrier.wait()
        return Resource()

    with ThreadPoolExecutor(thread_count) as pool:
        instances = list(pool.map(build, range(thread_count)))

    assert len(created) == 1
    assert all(instance is created[0] for instance in instances)


def test_short_secret_key_stops_startup(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "too-short")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        object.__new__(Settings).__init__()
