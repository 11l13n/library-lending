"""Учёт выдачи книг: консольное приложение.

ПР1 - начальный сценарий, ПР2 - коллекции, модули и JSON,
ПР3 - объектная модель: Book, Reader, Loan.
"""

from datetime import date
from typing import List, Optional

from models import Book, Loan, Reader
from models.books import (
    add_book,
    find_book_by_id,
    find_books,
    show_books,
    sort_books,
)
from models.loans import (
    get_book_status,
    get_statistics,
    is_book_available,
    issue_book,
    iter_active_loans,
    return_book,
    show_loans,
)
from models.readers import add_reader, find_reader_by_ticket, show_readers
from storage import (
    StorageError,
    load_books,
    load_loans,
    load_readers,
    save_books,
    save_loans,
    save_readers,
)
from utils import format_date, input_date, input_int, input_text

MENU = """
=== Учёт выдачи книг ===
1. Показать каталог
2. Найти книгу
3. Проверить доступность книги
4. Добавить книгу
5. Показать читателей
6. Добавить читателя
7. Выдать книгу
8. Оформить возврат
9. Показать текущие выдачи
10. Статистика
0. Выход"""


def select_book(books: List[Book]) -> Optional[Book]:
    """Запросить номер книги и вернуть объект Book."""
    book = find_book_by_id(books, input_int("Номер книги: "))
    if book is None:
        print("Книга с таким номером не найдена.")
    return book


def handle_check(books: List[Book], loans: List[Loan]) -> None:
    """Проверить доступность выбранной книги."""
    book = select_book(books)
    if book is not None:
        available = is_book_available(loans, book)
        print(f"{book.info}: {get_book_status(not available)}")


def handle_add_reader(readers: List[Reader]) -> bool:
    """Добавить читателя; вернуть True, если данные изменились."""
    try:
        reader = add_reader(
            readers,
            input_text("Имя: "),
            input_text("Номер билета: "),
        )
    except ValueError as error:
        print(f"Ошибка: {error}.")
        return False
    print(f"Читатель добавлен: {reader.name}.")
    return True


def handle_issue(
    books: List[Book],
    readers: List[Reader],
    loans: List[Loan],
) -> bool:
    """Выдать книгу читателю; вернуть True, если данные изменились."""
    book = select_book(books)
    if book is None:
        return False
    reader = find_reader_by_ticket(readers, input_text("Номер билета: "))
    if reader is None:
        print("Читатель с таким билетом не найден.")
        return False
    loan = issue_book(loans, book, reader, input_date("Дата выдачи"))
    if loan is None:
        print(get_book_status(True))
        return False
    print(f"Книга выдана. Вернуть до {format_date(loan.due_date)}.")
    return True


def handle_return(books: List[Book], loans: List[Loan]) -> bool:
    """Оформить возврат книги; вернуть True, если данные изменились."""
    book = select_book(books)
    if book is None:
        return False
    return_date = input_date("Дата возврата")
    try:
        loan = return_book(loans, book, return_date)
    except ValueError as error:
        print(f"Ошибка: {error}.")
        return False
    if loan is None:
        print("Эта книга сейчас не выдана.")
        return False
    overdue_days = loan.overdue_days(return_date)
    if overdue_days > 0:
        print(
            f"Просрочка {overdue_days} дн., "
            f"штраф {loan.fine(return_date):.2f} руб."
        )
    else:
        print("Книга возвращена вовремя.")
    return True


def show_statistics(books: List[Book], loans: List[Loan]) -> None:
    """Вывести сводные показатели."""
    stats = get_statistics(books, loans, date.today())
    print(f"Книг в каталоге: {stats['books']}")
    print(f"Выдано сейчас: {stats['issued']}")
    print(f"Доступно: {stats['available']}")
    print(f"Просрочено: {stats['overdue']}")
    print(f"Всего выдач за всё время: {stats['loans_total']}")


def main() -> None:
    """Точка запуска: загрузка данных и цикл меню."""
    try:
        books = load_books()
        readers = load_readers()
        loans = load_loans(books, readers)
    except StorageError as error:
        print(f"Не удалось загрузить данные: {error}")
        return

    while True:
        print(MENU)
        choice = input("Выберите действие: ").strip()
        try:
            if choice == "1":
                show_books(sort_books(books))
            elif choice == "2":
                show_books(find_books(books, input_text("Запрос: ")))
            elif choice == "3":
                handle_check(books, loans)
            elif choice == "4":
                book = add_book(
                    books,
                    input_text("Название: "),
                    input_text("Автор: "),
                )
                save_books(books)
                print(f"Книга добавлена под номером {book.id}.")
            elif choice == "5":
                show_readers(readers)
            elif choice == "6":
                if handle_add_reader(readers):
                    save_readers(readers)
            elif choice == "7":
                if handle_issue(books, readers, loans):
                    save_loans(loans)
            elif choice == "8":
                if handle_return(books, loans):
                    save_loans(loans)
            elif choice == "9":
                show_loans(list(iter_active_loans(loans)))
            elif choice == "10":
                show_statistics(books, loans)
            elif choice == "0":
                print("До свидания!")
                break
            else:
                print("Нет такого пункта меню.")
        except StorageError as error:
            print(f"Ошибка сохранения: {error}")


if __name__ == "__main__":
    main()
