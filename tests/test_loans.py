from datetime import date

import pytest

from models import Book, Loan, Reader
from models.loans import (
    calculate_due_date,
    calculate_fine,
    calculate_overdue_days,
    get_book_status,
    get_statistics,
    is_book_available,
    issue_book,
    return_book,
)

BOOK = Book(1, "Мастер и Маргарита", "М. А. Булгаков")
READER = Reader(1, "Иван Петров", "Б-0042")


def test_pr1_functions_are_kept():
    assert calculate_due_date(date(2026, 9, 1)) == date(2026, 9, 15)
    assert calculate_overdue_days(date(2026, 9, 15), date(2026, 9, 20)) == 5
    assert calculate_fine(5) == 50.0
    assert get_book_status(False) == "Книга доступна для выдачи"


def test_loan_links_book_and_reader():
    loan = Loan(1, BOOK, READER, date(2026, 9, 1))
    assert loan.book.title == "Мастер и Маргарита"
    assert loan.reader.ticket == "Б-0042"
    assert loan.is_active
    assert loan.due_date == date(2026, 9, 15)


def test_close_loan_and_fine():
    loan = Loan(1, BOOK, READER, date(2026, 9, 1))
    loan.close(date(2026, 9, 20))
    assert not loan.is_active
    assert loan.overdue_days(date(2026, 12, 31)) == 5
    assert loan.fine(date(2026, 12, 31)) == 50.0


def test_loan_cannot_be_closed_twice_or_before_issue():
    loan = Loan(1, BOOK, READER, date(2026, 9, 10))
    with pytest.raises(ValueError):
        loan.close(date(2026, 9, 1))
    loan.close(date(2026, 9, 12))
    with pytest.raises(ValueError):
        loan.close(date(2026, 9, 13))


def test_issued_book_is_not_available():
    loans = []
    assert issue_book(loans, BOOK, READER, date(2026, 9, 1)) is not None
    assert not is_book_available(loans, BOOK)
    assert issue_book(loans, BOOK, READER, date(2026, 9, 2)) is None


def test_return_makes_book_available_and_keeps_history():
    loans = []
    issue_book(loans, BOOK, READER, date(2026, 9, 1))
    loan = return_book(loans, BOOK, date(2026, 9, 10))
    assert loan.return_date == date(2026, 9, 10)
    assert is_book_available(loans, BOOK)
    assert len(loans) == 1


def test_statistics():
    other = Book(2, "Евгений Онегин", "А. С. Пушкин")
    loans = [Loan(1, BOOK, READER, date(2026, 9, 1))]
    stats = get_statistics([BOOK, other], loans, date(2026, 10, 1))
    assert stats == {
        "books": 2,
        "issued": 1,
        "available": 1,
        "overdue": 1,
        "loans_total": 1,
    }
