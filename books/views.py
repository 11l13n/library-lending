"""Страницы каталога библиотеки."""

from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render
from django.utils import timezone

from loans.models import Loan
from utils import parse_iso_date

from .models import Book, Casefold


def books(request):
    active_loans = Loan.objects.filter(
        book_id=OuterRef("pk"), return_date__isnull=True,
    )
    books_list = list(Book.objects.annotate(
        is_issued=Exists(active_loans),
    ).order_by("title", "id"))
    context = {
        "books": books_list,
        "issued_count": sum(book.is_issued for book in books_list),
    }
    return render(request, "books/book_list.html", context)


def search(request):
    query = request.GET.get("q", "").strip()
    books_list = Book.objects.none()
    if query:
        books_list = Book.objects.alias(
            folded_title=Casefold("title"), folded_author=Casefold("author"),
        ).filter(
            Q(folded_title__contains=query.casefold())
            | Q(folded_author__contains=query.casefold()),
        ).order_by("title", "id")
    return render(request, "books/search.html", {
        "query": query, "books": books_list,
    })


def available(request):
    check_date = parse_iso_date(request.GET.get("date"), timezone.localdate())
    occupied = Loan.objects.filter(
        Q(return_date__isnull=True) | Q(return_date__gt=check_date),
        book_id=OuterRef("pk"), issue_date__lte=check_date,
    )
    books_list = Book.objects.exclude(Exists(occupied)).order_by("title", "id")
    return render(request, "books/available.html", {
        "books": books_list, "check_date": check_date,
    })


def book_detail(request, book_id):
    book = Book.objects.filter(pk=book_id).first()
    history = []
    if book:
        history = list(book.loans.select_related("reader").order_by(
            "-issue_date", "-id",
        ))
    active_loan = next(
        (loan for loan in history if loan.return_date is None), None,
    )
    return render(request, "books/book_detail.html", {
        "book": book, "history": history, "active_loan": active_loan,
    }, status=200 if book else 404)
