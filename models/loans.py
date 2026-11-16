"""Класс Loan и функции выдачи и возврата книг."""

from datetime import date, timedelta
from typing import Any, Iterator, List, Optional

from utils import format_date, generate_id

from .base import LibraryObject
from .books import Book
from .readers import Reader

LOAN_PERIOD_DAYS = 14
FINE_PER_DAY = 10.0


def get_book_status(is_issued: bool) -> str:
    """Вернуть текстовый статус книги (функция из ПР1)."""
    if is_issued:
        return "Книга выдана другому читателю"
    return "Книга доступна для выдачи"


def calculate_due_date(
    issue_date: date,
    loan_days: int = LOAN_PERIOD_DAYS,
) -> date:
    """Рассчитать дату, до которой книгу нужно вернуть (из ПР1)."""
    return issue_date + timedelta(days=loan_days)


def calculate_overdue_days(due_date: date, return_date: date) -> int:
    """Посчитать количество дней просрочки (из ПР1)."""
    days = (return_date - due_date).days
    if days > 0:
        return days
    return 0


def calculate_fine(overdue_days: int) -> float:
    """Рассчитать штраф за просрочку возврата (из ПР1)."""
    if overdue_days == 0:
        return 0.0
    return overdue_days * FINE_PER_DAY


class Loan(LibraryObject):
    """Выдача книги читателю.

    Дата возврата хранится в закрытом атрибуте и меняется только
    методом close(): так нельзя «вернуть» книгу дважды или раньше
    даты выдачи.
    """

    def __init__(
        self,
        loan_id: int,
        book: Book,
        reader: Reader,
        issue_date: date,
        return_date: Optional[date] = None,
    ) -> None:
        super().__init__(loan_id)
        self.book = book
        self.reader = reader
        self.issue_date = issue_date
        self._return_date: Optional[date] = None
        if return_date is not None:
            self.close(return_date)

    @property
    def return_date(self) -> Optional[date]:
        """Дата возврата или None, если книга ещё у читателя."""
        return self._return_date

    @property
    def is_active(self) -> bool:
        """Выдача не завершена: книга находится у читателя."""
        return self._return_date is None

    @property
    def due_date(self) -> date:
        """Дата, до которой книгу нужно вернуть."""
        return calculate_due_date(self.issue_date)

    def close(self, return_date: date) -> None:
        """Оформить возврат книги."""
        if not self.is_active:
            raise ValueError("Книга по этой выдаче уже возвращена")
        if return_date < self.issue_date:
            raise ValueError("Дата возврата раньше даты выдачи")
        self._return_date = return_date

    def overdue_days(self, today: date) -> int:
        """Дни просрочки на дату возврата или на сегодня."""
        end_date = self._return_date or today
        return calculate_overdue_days(self.due_date, end_date)

    def fine(self, today: date) -> float:
        """Штраф за просрочку по этой выдаче."""
        return calculate_fine(self.overdue_days(today))

    def to_data(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "book_id": self.book.id,
            "reader_id": self.reader.id,
            "issue_date": self.issue_date.isoformat(),
            "return_date": (
                self._return_date.isoformat() if self._return_date else None
            ),
        }

    def __str__(self) -> str:
        text = (
            f"{self.id:>3}. {self.book.info} - {self.reader.name}, "
            f"выдана {format_date(self.issue_date)}"
        )
        if self.is_active:
            return f"{text}, вернуть до {format_date(self.due_date)}"
        return f"{text}, возвращена {format_date(self._return_date)}"


def iter_active_loans(loans: List[Loan]) -> Iterator[Loan]:
    """Перебрать незавершённые выдачи (генератор)."""
    for loan in loans:
        if loan.is_active:
            yield loan


def find_active_loan(loans: List[Loan], book: Book) -> Optional[Loan]:
    """Найти незавершённую выдачу книги."""
    for loan in iter_active_loans(loans):
        if loan.book.id == book.id:
            return loan
    return None


def find_loan_by_id(loans: List[Loan], loan_id: int) -> Optional[Loan]:
    """Найти выдачу по идентификатору."""
    for loan in loans:
        if loan.id == loan_id:
            return loan
    return None


def is_book_available(loans: List[Loan], book: Book) -> bool:
    """Проверить, что у книги нет незавершённой выдачи."""
    return find_active_loan(loans, book) is None


def issue_book(
    loans: List[Loan],
    book: Book,
    reader: Reader,
    issue_date: date,
) -> Optional[Loan]:
    """Выдать книгу читателю; вернуть None, если книга уже выдана."""
    if not is_book_available(loans, book):
        return None
    loan = Loan(generate_id(loan.id for loan in loans), book, reader,
                issue_date)
    loans.append(loan)
    return loan


def return_book(
    loans: List[Loan],
    book: Book,
    return_date: date,
) -> Optional[Loan]:
    """Оформить возврат книги; вернуть закрытую выдачу или None."""
    loan = find_active_loan(loans, book)
    if loan is not None:
        loan.close(return_date)
    return loan


def get_overdue_loans(loans: List[Loan], today: date) -> List[Loan]:
    """Вернуть незавершённые выдачи с истёкшим сроком возврата."""
    return [
        loan for loan in iter_active_loans(loans)
        if loan.overdue_days(today) > 0
    ]


def get_statistics(
    books: List[Book],
    loans: List[Loan],
    today: date,
) -> dict[str, int]:
    """Посчитать сводные показатели библиотеки."""
    issued = sum(1 for _ in iter_active_loans(loans))
    return {
        "books": len(books),
        "issued": issued,
        "available": len(books) - issued,
        "overdue": len(get_overdue_loans(loans, today)),
        "loans_total": len(loans),
    }


def show_loans(loans: List[Loan]) -> None:
    """Вывести выдачи."""
    if not loans:
        print("Выдач нет.")
    for loan in loans:
        print(loan)
