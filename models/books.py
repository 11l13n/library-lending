"""Класс Book и функции работы с каталогом книг."""

from typing import Any, Iterator, List, Optional

from utils import generate_id

from .base import LibraryObject


class Book(LibraryObject):
    """Экземпляр книги в каталоге библиотеки."""

    def __init__(self, book_id: int, title: str, author: str) -> None:
        super().__init__(book_id)
        if not Book.validate_text(title) or not Book.validate_text(author):
            raise ValueError("Название и автор не могут быть пустыми")
        self.title = title.strip()
        self.author = author.strip()

    @staticmethod
    def validate_text(value: str) -> bool:
        """Проверить, что строка не пустая."""
        return isinstance(value, str) and bool(value.strip())

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "Book":
        """Создать книгу из словаря, прочитанного из JSON."""
        return cls(data["id"], data["title"], data["author"])

    def to_data(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "author": self.author}

    @property
    def info(self) -> str:
        """Краткое описание книги для вывода."""
        return f"«{self.title}», {self.author}"

    def matches(self, query: str) -> bool:
        """Проверить, встречается ли query в названии или авторе."""
        query = query.casefold()
        return (
            query in self.title.casefold()
            or query in self.author.casefold()
        )

    def __str__(self) -> str:
        return f"{self.id:>3}. {self.title} - {self.author}"


def add_book(books: List[Book], title: str, author: str) -> Book:
    """Создать книгу, добавить её в каталог и вернуть."""
    book = Book(generate_id(book.id for book in books), title, author)
    books.append(book)
    return book


def find_book_by_id(books: List[Book], book_id: int) -> Optional[Book]:
    """Найти книгу по идентификатору."""
    for book in books:
        if book.id == book_id:
            return book
    return None


def find_books(books: List[Book], query: str) -> List[Book]:
    """Найти книги по подстроке названия или автора."""
    return [book for book in books if book.matches(query)]


def iter_books_by_author(books: List[Book], author: str) -> Iterator[Book]:
    """Перебрать книги указанного автора (генератор)."""
    author = author.casefold()
    for book in books:
        if author in book.author.casefold():
            yield book


def sort_books(books: List[Book], field: str = "title") -> List[Book]:
    """Вернуть книги, отсортированные по названию или автору."""
    return sorted(books, key=lambda book: getattr(book, field).casefold())


def show_books(books: List[Book]) -> None:
    """Вывести список книг."""
    if not books:
        print("Книги не найдены.")
    for book in books:
        print(book)
