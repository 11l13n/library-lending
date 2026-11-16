"""Загрузка и сохранение данных проекта в JSON-файлах."""

import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List

from models import Book, LibraryObject, Loan, Reader

DATA_DIR = Path(__file__).resolve().parent / "data"
BOOKS_FILE = DATA_DIR / "books.json"
READERS_FILE = DATA_DIR / "readers.json"
LOANS_FILE = DATA_DIR / "loans.json"


class StorageError(Exception):
    """Ошибка чтения или записи файла данных."""


def read_json(filename: Path) -> list[dict[str, Any]]:
    """Прочитать список записей из JSON-файла.

    Отсутствующий файл считается пустым списком, повреждённый файл
    приводит к StorageError.
    """
    try:
        with open(filename, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise StorageError(f"Файл {filename} повреждён: {error}") from error
    except (OSError, UnicodeError) as error:
        message = f"Не удалось прочитать {filename}: {error}"
        raise StorageError(message) from error
    if not isinstance(data, list):
        raise StorageError(f"Файл {filename} должен содержать список")
    if any(not isinstance(record, dict) for record in data):
        raise StorageError(f"Записи в {filename} должны быть словарями")
    return data


def write_json(filename: Path, records: list[dict[str, Any]]) -> None:
    """Записать список записей в JSON-файл."""
    try:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=4)
    except OSError as error:
        message = f"Не удалось записать {filename}: {error}"
        raise StorageError(message) from error


def save_objects(filename: Path, objects: Iterable[LibraryObject]) -> None:
    """Сохранить объекты учёта: каждый объект сам формирует свой словарь."""
    write_json(filename, [obj.to_data() for obj in objects])


def load_books(filename: Path = BOOKS_FILE) -> List[Book]:
    """Загрузить каталог книг: JSON -> объекты Book."""
    try:
        return [Book.from_data(data) for data in read_json(filename)]
    except (KeyError, TypeError, ValueError) as error:
        raise StorageError(f"Некорректные данные в {filename}") from error


def save_books(books: List[Book], filename: Path = BOOKS_FILE) -> None:
    """Сохранить каталог книг: объекты Book -> JSON."""
    save_objects(filename, books)


def load_readers(filename: Path = READERS_FILE) -> List[Reader]:
    """Загрузить читателей: JSON -> объекты Reader."""
    try:
        return [Reader.from_data(data) for data in read_json(filename)]
    except (KeyError, TypeError, ValueError) as error:
        raise StorageError(f"Некорректные данные в {filename}") from error


def save_readers(
    readers: List[Reader],
    filename: Path = READERS_FILE,
) -> None:
    """Сохранить читателей: объекты Reader -> JSON."""
    save_objects(filename, readers)


def load_loans(
    books: List[Book],
    readers: List[Reader],
    filename: Path = LOANS_FILE,
) -> List[Loan]:
    """Загрузить выдачи: идентификаторы из JSON заменяются объектами."""
    books_by_id = {book.id: book for book in books}
    readers_by_id = {reader.id: reader for reader in readers}
    loans = []
    try:
        for data in read_json(filename):
            return_date = data["return_date"]
            loans.append(Loan(
                data["id"],
                books_by_id[data["book_id"]],
                readers_by_id[data["reader_id"]],
                date.fromisoformat(data["issue_date"]),
                date.fromisoformat(return_date) if return_date else None,
            ))
    except (KeyError, TypeError, ValueError) as error:
        raise StorageError(f"Некорректные данные в {filename}") from error
    return loans


def save_loans(loans: List[Loan], filename: Path = LOANS_FILE) -> None:
    """Сохранить выдачи: объекты Loan -> JSON с идентификаторами."""
    save_objects(filename, loans)
