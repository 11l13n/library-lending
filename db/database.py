"""Подключение к базе данных SQLite."""

import sqlite3
from pathlib import Path
from typing import Any, Sequence

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "library.sqlite"
SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"


def casefold(value: Any) -> Any:
    """Привести строку к нижнему регистру с учётом кириллицы.

    Встроенные LOWER() и LIKE в SQLite не различают регистр только
    для латиницы, поэтому для поиска регистрируется функция Python.
    """
    return value.casefold() if isinstance(value, str) else value


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Открыть соединение и включить проверку внешних ключей."""
    conn = sqlite3.connect(DB_PATH if db_path is None else db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("casefold", 1, casefold, deterministic=True)
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Создать таблицы по файлу sql/schema.sql."""
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def fetch_all(
    query: str,
    params: Sequence[Any] = (),
    db_path: Path | None = None,
) -> list[sqlite3.Row]:
    """Выполнить SELECT и вернуть строки с доступом к полям по имени."""
    conn = get_connection(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def fetch_one(
    query: str,
    params: Sequence[Any] = (),
    db_path: Path | None = None,
) -> sqlite3.Row | None:
    """Выполнить SELECT и вернуть первую строку или None."""
    conn = get_connection(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchone()
    finally:
        conn.close()
