from datetime import date

import pytest

from models import Book, Loan, Reader
from storage import (
    StorageError,
    load_books,
    load_loans,
    read_json,
    save_books,
    save_loans,
)


def test_missing_file_gives_empty_list(tmp_path):
    assert read_json(tmp_path / "missing.json") == []


def test_broken_json_raises_storage_error(tmp_path):
    filename = tmp_path / "broken.json"
    filename.write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError):
        read_json(filename)


def test_books_round_trip(tmp_path):
    filename = tmp_path / "books.json"
    save_books([Book(1, "Обломов", "И. А. Гончаров")], filename)
    books = load_books(filename)
    assert books[0].title == "Обломов"


def test_loans_are_restored_with_linked_objects(tmp_path):
    filename = tmp_path / "loans.json"
    book = Book(1, "Обломов", "И. А. Гончаров")
    reader = Reader(1, "Иван Петров", "Б-0042")
    save_loans([Loan(1, book, reader, date(2026, 9, 1))], filename)
    loan = load_loans([book], [reader], filename)[0]
    assert loan.book is book
    assert loan.reader is reader
    assert loan.is_active


def test_loan_with_unknown_book_is_error(tmp_path):
    filename = tmp_path / "loans.json"
    book = Book(1, "Обломов", "И. А. Гончаров")
    reader = Reader(1, "Иван Петров", "Б-0042")
    save_loans([Loan(1, book, reader, date(2026, 9, 1))], filename)
    with pytest.raises(StorageError):
        load_loans([], [reader], filename)


@pytest.mark.parametrize("records", [
    [None], ["book"], [{"id": "1", "title": "Книга", "author": "Автор"}],
    [{"id": True, "title": "Книга", "author": "Автор"}],
    [{"id": 1, "title": None, "author": "Автор"}],
    [{"id": 1, "title": "Книга"}],
])
def test_malformed_records_raise_storage_error(tmp_path, records):
    import json

    filename = tmp_path / "books.json"
    filename.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(StorageError):
        load_books(filename)


def test_file_read_error_is_wrapped(tmp_path):
    with pytest.raises(StorageError, match="Не удалось прочитать"):
        read_json(tmp_path)


def test_invalid_utf8_is_wrapped(tmp_path):
    filename = tmp_path / "books.json"
    filename.write_bytes(b"\xff\xfe")
    with pytest.raises(StorageError):
        read_json(filename)
