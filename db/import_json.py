"""Перенос данных из JSON-файлов в базу SQLite.

Запуск из корня проекта: python -m db.import_json
Повторный запуск безопасен: таблицы создаются при отсутствии,
старые записи удаляются перед загрузкой.
"""

import sqlite3
from pathlib import Path

from db.database import DB_PATH, create_schema, get_connection
from storage import (
    BOOKS_FILE,
    LOANS_FILE,
    READERS_FILE,
    StorageError,
    load_books,
    load_loans,
    load_readers,
)


def clear_tables(conn: sqlite3.Connection) -> None:
    """Удалить записи: сначала зависимые выдачи, затем книги и читателей."""
    conn.execute("DELETE FROM loans")
    conn.execute("DELETE FROM books")
    conn.execute("DELETE FROM readers")


def import_all(
    db_path: Path = DB_PATH,
    books_file: Path = BOOKS_FILE,
    readers_file: Path = READERS_FILE,
    loans_file: Path = LOANS_FILE,
) -> dict[str, int]:
    """Проверить JSON и заменить данные в одной транзакции."""
    # Для консоли отсутствие файла означает пустую коллекцию. При импорте
    # это ошибка: иначе можно случайно очистить уже заполненную базу.
    for filename in (books_file, readers_file, loans_file):
        if not Path(filename).is_file():
            raise StorageError(f"Не найден исходный файл: {filename}")
    books = load_books(books_file)
    readers = load_readers(readers_file)
    loans = load_loans(books, readers, loans_file)
    conn = get_connection(db_path)
    try:
        create_schema(conn)
        clear_tables(conn)
        # Выдачи ссылаются на книги и читателей, поэтому идут последними.
        conn.executemany(
            "INSERT INTO books (id, title, author) VALUES (?, ?, ?)",
            [(book.id, book.title, book.author) for book in books],
        )
        conn.executemany(
            "INSERT INTO readers (id, name, ticket) VALUES (?, ?, ?)",
            [(reader.id, reader.name, reader.ticket) for reader in readers],
        )
        conn.executemany(
            """
            INSERT INTO loans
                (id, book_id, reader_id, issue_date, return_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (loan.id, loan.book.id, loan.reader.id,
                 loan.issue_date.isoformat(),
                 loan.return_date.isoformat() if loan.return_date else None)
                for loan in loans
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"books": len(books), "readers": len(readers), "loans": len(loans)}


def main() -> None:
    counts = import_all()
    print(
        f"Перенесено: книг - {counts['books']}, "
        f"читателей - {counts['readers']}, выдач - {counts['loans']}"
    )


if __name__ == "__main__":
    main()
