"""Страницы каталога: данные читаются из SQLite SQL-запросами."""

from django.shortcuts import render
from django.utils import timezone

from db.database import fetch_all, fetch_one
from utils import parse_iso_date


def books(request):
    books_list = fetch_all("""
        SELECT
            books.id,
            books.title,
            books.author,
            loans.id AS active_loan_id
        FROM books
        LEFT JOIN loans
            ON loans.book_id = books.id
            AND loans.return_date IS NULL
        ORDER BY books.title, books.id
    """)
    context = {
        "books": books_list,
        "issued_count": sum(1 for book in books_list
                            if book["active_loan_id"]),
    }
    return render(request, "books/book_list.html", context)


def search(request):
    query = request.GET.get("q", "").strip()
    books_list = []
    if query:
        books_list = fetch_all(
            """
            SELECT id, title, author
            FROM books
            WHERE casefold(title) LIKE '%' || casefold(?) || '%'
               OR casefold(author) LIKE '%' || casefold(?) || '%'
            ORDER BY title
            """,
            [query, query],
        )
    context = {"query": query, "books": books_list}
    return render(request, "books/search.html", context)


def available(request):
    check_date = parse_iso_date(request.GET.get("date"), timezone.localdate())
    books_list = fetch_all("""
        SELECT id, title, author
        FROM books
        WHERE id NOT IN (
            SELECT book_id
            FROM loans
            WHERE issue_date <= ?
              AND (return_date IS NULL OR return_date > ?)
        )
        ORDER BY title
    """, [check_date.isoformat(), check_date.isoformat()])
    context = {"books": books_list, "check_date": check_date}
    return render(request, "books/available.html", context)


def book_detail(request, book_id):
    book = fetch_one(
        "SELECT id, title, author FROM books WHERE id = ?",
        [book_id],
    )
    history = []
    if book is not None:
        history = fetch_all(
            """
            SELECT
                loans.id,
                readers.name AS reader_name,
                strftime('%d.%m.%Y', loans.issue_date) AS issue_date,
                strftime('%d.%m.%Y', date(loans.issue_date, '+14 days'))
                    AS due_date,
                strftime('%d.%m.%Y', loans.return_date) AS return_date
            FROM loans
            JOIN readers ON loans.reader_id = readers.id
            WHERE loans.book_id = ?
            ORDER BY loans.issue_date DESC
            """,
            [book_id],
        )
    active_loan = next(
        (loan for loan in history if loan["return_date"] is None),
        None,
    )
    context = {
        "book": book,
        "history": history,
        "active_loan": active_loan,
    }
    return render(
        request,
        "books/book_detail.html",
        context,
        status=404 if book is None else 200,
    )
