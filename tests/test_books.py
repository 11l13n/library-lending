import pytest

from models import Book
from models.books import (
    add_book,
    find_book_by_id,
    find_books,
    iter_books_by_author,
    sort_books,
)


def make_books():
    books = []
    add_book(books, "Мастер и Маргарита", "М. А. Булгаков")
    add_book(books, "Евгений Онегин", "А. С. Пушкин")
    add_book(books, "Капитанская дочка", "А. С. Пушкин")
    return books


def test_book_attributes_and_str():
    book = Book(1, "Мёртвые души", "Н. В. Гоголь")
    assert book.title == "Мёртвые души"
    assert book.info == "«Мёртвые души», Н. В. Гоголь"
    assert "Мёртвые души - Н. В. Гоголь" in str(book)


def test_empty_title_is_rejected():
    with pytest.raises(ValueError):
        Book(1, "  ", "Автор")


def test_add_book_creates_object_with_next_id():
    books = make_books()
    book = add_book(books, "Мёртвые души", "Н. В. Гоголь")
    assert isinstance(book, Book)
    assert book.id == 4
    assert find_book_by_id(books, 4) is book


def test_find_books_uses_matches_method():
    books = make_books()
    assert [book.id for book in find_books(books, "пушкин")] == [2, 3]


def test_iter_books_by_author_is_generator():
    books = make_books()
    titles = [book.title for book in iter_books_by_author(books, "Пушкин")]
    assert titles == ["Евгений Онегин", "Капитанская дочка"]


def test_sort_books_by_title():
    books = make_books()
    assert sort_books(books)[0].title == "Евгений Онегин"


def test_from_data_and_to_data_are_symmetric():
    data = {"id": 7, "title": "Обломов", "author": "И. А. Гончаров"}
    assert Book.from_data(data).to_data() == data
