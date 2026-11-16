import json
import sqlite3
from pathlib import Path

import pytest

from db.database import fetch_all, fetch_one, get_connection
from db.import_json import import_all
from storage import StorageError

BOOKS = [
    {"id": 1, "title": "Мастер и Маргарита", "author": "М. А. Булгаков"},
    {"id": 2, "title": "Евгений Онегин", "author": "А. С. Пушкин"},
    {"id": 3, "title": "Капитанская дочка", "author": "А. С. Пушкин"},
]
READERS = [
    {"id": 1, "name": "Иван Петров", "ticket": "Б-0042"},
    {"id": 2, "name": "Анна Смирнова", "ticket": "Б-0043"},
]
LOANS = [
    {"id": 1, "book_id": 1, "reader_id": 1,
     "issue_date": "2026-09-01", "return_date": "2026-09-20"},
    {"id": 2, "book_id": 2, "reader_id": 1,
     "issue_date": "2026-09-10", "return_date": None},
    {"id": 3, "book_id": 1, "reader_id": 2,
     "issue_date": "2026-10-01", "return_date": None},
    {"id": 4, "book_id": 3, "reader_id": 1,
     "issue_date": "2026-09-05", "return_date": "2026-09-08"},
]


@pytest.fixture
def db_path(tmp_path):
    """Временная база, заполненная тестовыми JSON-файлами."""
    files = {}
    for name, records in (
        ("books", BOOKS), ("readers", READERS), ("loans", LOANS),
    ):
        files[name] = tmp_path / f"{name}.json"
        files[name].write_text(json.dumps(records), encoding="utf-8")
    path = tmp_path / "library.sqlite"
    import_all(path, files["books"], files["readers"], files["loans"])
    return path


def test_import_matches_json_files(db_path):
    summary = fetch_one(
        "SELECT (SELECT COUNT(*) FROM books) AS books, "
        "(SELECT COUNT(*) FROM readers) AS readers, "
        "(SELECT COUNT(*) FROM loans) AS loans",
        db_path=db_path,
    )
    assert (summary["books"], summary["readers"], summary["loans"]) == (
        3, 2, 4,
    )


def test_import_can_be_repeated(db_path, tmp_path):
    counts = import_all(
        db_path,
        tmp_path / "books.json",
        tmp_path / "readers.json",
        tmp_path / "loans.json",
    )
    assert counts == {"books": 3, "readers": 2, "loans": 4}


def test_foreign_keys_are_checked(db_path):
    conn = get_connection(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO loans (book_id, reader_id, issue_date) "
            "VALUES (?, ?, ?)",
            [999, 1, "2026-10-01"],
        )
    conn.close()


def test_search_ignores_cyrillic_case(db_path):
    rows = fetch_all(
        "SELECT title FROM books "
        "WHERE casefold(author) LIKE '%' || casefold(?) || '%' "
        "ORDER BY title",
        ["пушкин"],
        db_path=db_path,
    )
    assert [row["title"] for row in rows] == [
        "Евгений Онегин",
        "Капитанская дочка",
    ]


def test_available_books_exclude_active_loans(db_path):
    rows = fetch_all(
        "SELECT id FROM books WHERE id NOT IN "
        "(SELECT book_id FROM loans WHERE return_date IS NULL)",
        db_path=db_path,
    )
    assert [row["id"] for row in rows] == [3]


def test_loans_grouped_by_reader_with_having(db_path):
    rows = fetch_all(
        "SELECT readers.name, COUNT(loans.id) AS loans_count "
        "FROM readers JOIN loans ON loans.reader_id = readers.id "
        "GROUP BY readers.id, readers.name "
        "HAVING COUNT(loans.id) > ? ORDER BY loans_count DESC",
        [1],
        db_path=db_path,
    )
    assert [(row["name"], row["loans_count"]) for row in rows] == [
        ("Иван Петров", 3),
    ]


@pytest.mark.parametrize("error_kind", ["missing", "json", "date"])
def test_invalid_import_preserves_existing_database(
    db_path, tmp_path, error_kind,
):
    source = tmp_path / "loans.json"
    if error_kind == "missing":
        source.unlink()
    elif error_kind == "json":
        source.write_text("{broken", encoding="utf-8")
    else:
        records = [dict(LOANS[0], return_date="2026-08-01")]
        source.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(StorageError):
        import_all(db_path, tmp_path / "books.json",
                   tmp_path / "readers.json", source)
    assert fetch_one("SELECT COUNT(*) AS n FROM loans",
                     db_path=db_path)["n"] == 4
    assert fetch_one("SELECT COUNT(*) AS n FROM books",
                     db_path=db_path)["n"] == 3


def test_sql_error_rolls_back_import(db_path, tmp_path):
    records = [dict(READERS[0]), dict(READERS[1], ticket=READERS[0]["ticket"])]
    (tmp_path / "readers.json").write_text(json.dumps(records),
                                           encoding="utf-8")
    with pytest.raises(sqlite3.IntegrityError):
        import_all(db_path, tmp_path / "books.json",
                   tmp_path / "readers.json", tmp_path / "loans.json")
    reader = fetch_one("SELECT ticket FROM readers WHERE id = 2",
                       db_path=db_path)
    assert reader["ticket"] == "Б-0043"
    assert fetch_one("SELECT COUNT(*) AS n FROM loans",
                     db_path=db_path)["n"] == 4


def test_all_documented_sql_queries_execute(db_path):
    source = Path(__file__).resolve().parents[1] / "sql" / "queries.sql"
    statements = []
    statement = ""
    for line in source.read_text(encoding="utf-8").splitlines():
        statement += line + "\n"
        if sqlite3.complete_statement(statement):
            statements.append(statement)
            statement = ""
    parameters = [
        [], [], [1], ["пушкин", "пушкин"],
        ["2026-09-19", "2026-09-19"], [], [],
        ["2026-09-19"] * 4, ["2026-10-20", 1], [1], [], [], [],
        ["2026-10-20"], [], [1], [],
    ]
    assert len(statements) == len(parameters) == 17
    results = [fetch_all(query, params, db_path)
               for query, params in zip(statements, parameters)]
    assert {row["id"] for row in results[4]} == {3}
    assert results[7][0]["overdue_days"] == 4
    assert results[7][0]["fine"] == 40
