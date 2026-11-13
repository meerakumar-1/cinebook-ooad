"""PATTERN (Creational): Singleton - one shared SQLite connection for the whole app."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema.sql")


class DatabaseManager:
    _instance: "DatabaseManager | None" = None

    def __init__(self, path: str):
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA.read_text())

    @classmethod
    def get_instance(cls, path: str = "cinebook.db") -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = cls(path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:  # needed for tests
        if cls._instance:
            cls._instance._conn.close()
        cls._instance = None

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def transaction(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
