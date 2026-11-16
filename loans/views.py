"""Страницы выдач, читателей и статистики: данные из SQLite."""

from django.shortcuts import render
from django.utils import timezone

from db.database import fetch_all, fetch_one
from utils import parse_iso_date


def loans(request):
    loans_list = fetch_all("""
        SELECT
            loans.id,
            books.title AS book_title,
            readers.name AS reader_name,
            readers.ticket,
            strftime('%d.%m.%Y', loans.issue_date) AS issue_date,
            strftime('%d.%m.%Y', date(loans.issue_date, '+14 days'))
                AS due_date
        FROM loans
        JOIN books ON loans.book_id = books.id
        JOIN readers ON loans.reader_id = readers.id
        WHERE loans.return_date IS NULL
        ORDER BY loans.issue_date
    """)
    return render(request, "loans/loan_list.html", {"loans": loans_list})


def overdue(request):
    check_date = parse_iso_date(request.GET.get("date"), timezone.localdate())
    check_text = check_date.isoformat()
    loans_list = fetch_all(
        """
        SELECT
            loans.id,
            books.title AS book_title,
            readers.name AS reader_name,
            readers.ticket,
            strftime('%d.%m.%Y', date(loans.issue_date, '+14 days'))
                AS due_date,
            CAST(julianday(?) - julianday(loans.issue_date, '+14 days')
                 AS INTEGER) AS overdue_days,
            CAST(julianday(?) - julianday(loans.issue_date, '+14 days')
                 AS INTEGER) * 10 AS fine
        FROM loans
        JOIN books ON loans.book_id = books.id
        JOIN readers ON loans.reader_id = readers.id
        WHERE (loans.return_date IS NULL OR loans.return_date > ?)
          AND date(loans.issue_date, '+14 days') < ?
        ORDER BY overdue_days DESC
        """,
        [check_text, check_text, check_text, check_text],
    )
    context = {
        "loans": loans_list,
        "check_date": check_date,
        "total_fine": sum(loan["fine"] for loan in loans_list),
    }
    return render(request, "loans/overdue.html", context)


def loan_detail(request, loan_id):
    loan = fetch_one(
        """
        SELECT
            loans.id,
            loans.book_id,
            books.title AS book_title,
            books.author,
            readers.name AS reader_name,
            readers.ticket,
            strftime('%d.%m.%Y', loans.issue_date) AS issue_date,
            strftime('%d.%m.%Y', date(loans.issue_date, '+14 days'))
                AS due_date,
            strftime('%d.%m.%Y', loans.return_date) AS return_date,
            MAX(
                CAST(julianday(COALESCE(loans.return_date, ?))
                     - julianday(loans.issue_date, '+14 days') AS INTEGER),
                0
            ) AS overdue_days
        FROM loans
        JOIN books ON loans.book_id = books.id
        JOIN readers ON loans.reader_id = readers.id
        WHERE loans.id = ?
        """,
        [timezone.localdate().isoformat(), loan_id],
    )
    return render(
        request,
        "loans/loan_detail.html",
        {"loan": loan},
        status=404 if loan is None else 200,
    )


def readers(request):
    readers_list = fetch_all(
        """
        SELECT
            readers.id,
            readers.name,
            readers.ticket,
            COUNT(loans.id) AS loans_count,
            COUNT(loans.id) - COUNT(loans.return_date) AS on_hands,
            COALESCE(SUM(
                MAX(
                    CAST(julianday(COALESCE(loans.return_date, ?))
                         - julianday(loans.issue_date, '+14 days')
                         AS INTEGER),
                    0
                )
            ), 0) * 10 AS fine
        FROM readers
        LEFT JOIN loans ON loans.reader_id = readers.id
        GROUP BY readers.id, readers.name, readers.ticket
        ORDER BY loans_count DESC, readers.name
        """,
        [timezone.localdate().isoformat()],
    )
    return render(request, "loans/readers.html", {"readers": readers_list})


def statistics(request):
    try:
        min_loans = max(int(request.GET.get("min", 2)), 0)
    except ValueError:
        min_loans = 2
    summary = fetch_one("""
        SELECT
            (SELECT COUNT(*) FROM books) AS books_count,
            (SELECT COUNT(*) FROM readers) AS readers_count,
            COUNT(*) AS loans_count,
            COUNT(*) - COUNT(return_date) AS issued_count
        FROM loans
    """)
    durations = fetch_one("""
        SELECT
            ROUND(AVG(julianday(return_date) - julianday(issue_date)), 1)
                AS avg_days,
            MAX(julianday(return_date) - julianday(issue_date)) AS max_days
        FROM loans
        WHERE return_date IS NOT NULL
    """)
    popular_books = fetch_all("""
        SELECT
            books.id,
            books.title,
            books.author,
            COUNT(loans.id) AS loans_count
        FROM books
        LEFT JOIN loans ON loans.book_id = books.id
        GROUP BY books.id, books.title, books.author
        ORDER BY loans_count DESC, books.title
    """)
    by_month = fetch_all("""
        SELECT
            strftime('%Y-%m', issue_date) AS month,
            COUNT(*) AS loans_count
        FROM loans
        GROUP BY month
        ORDER BY month
    """)
    active_readers = fetch_all(
        """
        SELECT
            readers.name,
            COUNT(loans.id) AS loans_count
        FROM readers
        JOIN loans ON loans.reader_id = readers.id
        GROUP BY readers.id, readers.name
        HAVING COUNT(loans.id) > ?
        ORDER BY loans_count DESC
        """,
        [min_loans],
    )
    popular_authors = fetch_all("""
        SELECT
            books.author,
            COUNT(loans.id) AS loans_count
        FROM books
        JOIN loans ON loans.book_id = books.id
        GROUP BY books.author
        HAVING COUNT(loans.id) > 1
        ORDER BY loans_count DESC
    """)
    context = {
        "summary": summary,
        "durations": durations,
        "popular_books": popular_books,
        "by_month": by_month,
        "active_readers": active_readers,
        "min_loans": min_loans,
        "popular_authors": popular_authors,
    }
    return render(request, "loans/statistics.html", context)
