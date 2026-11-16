"""Страницы выдач, читателей и статистики."""

from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce, Round, TruncMonth
from django.shortcuts import render
from django.utils import timezone

from books.models import Book, Casefold
from models.loans import FINE_PER_DAY
from utils import parse_iso_date

from .models import Loan, Reader, days_between, overdue_days_expression

LOAN_ORDERING = {
    "oldest": ("issue_date", "id"),
    "newest": ("-issue_date", "-id"),
    "book": ("book__title", "id"),
    "reader": ("reader__name", "id"),
}


def loans(request):
    queryset = Loan.objects.with_people_and_books()
    status = request.GET.get("status", Loan.Status.ACTIVE)
    if status == Loan.Status.COMPLETED:
        queryset = queryset.completed()
    elif status == Loan.Status.CANCELLED:
        queryset = queryset.cancelled()
    elif status != "all":
        status = Loan.Status.ACTIVE
        queryset = queryset.active()
    issue_date = parse_iso_date(request.GET.get("date"), None)
    book = request.GET.get("book", "").strip()
    reader = request.GET.get("reader", "").strip()
    order = request.GET.get("sort", "oldest")
    if issue_date:
        queryset = queryset.filter(issue_date=issue_date)
    if book:
        queryset = queryset.alias(
            folded_book=Casefold("book__title"),
        ).filter(folded_book__contains=book.casefold())
    if reader:
        queryset = queryset.alias(
            folded_reader=Casefold("reader__name"),
            folded_ticket=Casefold("reader__ticket"),
        ).filter(
            Q(folded_reader__contains=reader.casefold())
            | Q(folded_ticket__contains=reader.casefold()),
        )
    if order not in LOAN_ORDERING:
        order = "oldest"
    page = Paginator(queryset.order_by(*LOAN_ORDERING[order]), 10).get_page(
        request.GET.get("page"),
    )
    return render(request, "loans/loan_list.html", {
        "loans": page.object_list, "page_obj": page, "issue_date": issue_date,
        "book_query": book, "reader_query": reader, "order": order,
        "status": status, "status_choices": Loan.Status.choices,
    })


def overdue(request):
    check_date = parse_iso_date(request.GET.get("date"), timezone.localdate())
    blocking = Loan.objects.blocking_on(check_date).with_people_and_books()
    loans_list = list(blocking.annotate(
        overdue_days=overdue_days_expression(
            Value(check_date), F("issue_date"),
        ),
        fine=F("overdue_days") * int(FINE_PER_DAY),
    ).filter(overdue_days__gt=0).order_by("-overdue_days", "id"))
    return render(request, "loans/overdue.html", {
        "loans": loans_list, "check_date": check_date,
        "total_fine": sum(loan.fine for loan in loans_list),
    })


def loan_detail(request, loan_id):
    today = timezone.localdate()
    loan = Loan.objects.with_people_and_books().with_penalty(
        today,
    ).filter(pk=loan_id).first()
    return render(request, "loans/loan_detail.html", {"loan": loan},
                  status=200 if loan else 404)


def readers(request):
    today = timezone.localdate()
    overdue_days = overdue_days_expression(
        Coalesce("loans__return_date", Value(today)), F("loans__issue_date"),
    )
    readers_list = Reader.objects.annotate(
        loans_count=Count("loans"),
        on_hands=Count("loans", filter=Q(loans__status=Loan.Status.ACTIVE)),
        fine=Sum(
            overdue_days, filter=~Q(loans__status=Loan.Status.CANCELLED),
            default=0,
        ) * int(FINE_PER_DAY),
    ).order_by("-loans_count", "name", "id").values(
        "id", "name", "ticket", "loans_count", "on_hands", "fine",
    )
    return render(request, "loans/readers.html", {"readers": readers_list})


def statistics(request):
    try:
        min_loans = max(int(request.GET.get("min", 2)), 0)
    except ValueError:
        min_loans = 2
    summary = Loan.objects.aggregate(
        loans_count=Count("pk"),
        issued_count=Count("pk", filter=Q(status=Loan.Status.ACTIVE)),
        completed_count=Count("pk", filter=Q(status=Loan.Status.COMPLETED)),
        cancelled_count=Count("pk", filter=Q(status=Loan.Status.CANCELLED)),
    )
    summary.update(books_count=Book.objects.count(),
                   readers_count=Reader.objects.count())
    durations = Loan.objects.completed().annotate(
        duration_days=days_between(F("return_date"), F("issue_date")),
    ).aggregate(avg_days=Round(Avg("duration_days"), 1),
                max_days=Max("duration_days"))
    popular_books = Book.objects.annotate(
        loans_count=Count("loans"),
    ).order_by("-loans_count", "title", "id")
    by_month = Loan.objects.annotate(month=TruncMonth("issue_date")).values(
        "month",
    ).annotate(loans_count=Count("pk")).order_by("month")
    active_readers = Reader.objects.annotate(
        loans_count=Count("loans"),
    ).filter(loans_count__gt=min_loans).order_by(
        "-loans_count", "id",
    ).values("name", "loans_count")
    popular_authors = Book.objects.values("author").annotate(
        loans_count=Count("loans"),
    ).filter(loans_count__gt=1).order_by("-loans_count", "author")
    return render(request, "loans/statistics.html", {
        "summary": summary, "durations": durations,
        "popular_books": popular_books, "by_month": by_month,
        "active_readers": active_readers, "min_loans": min_loans,
        "popular_authors": popular_authors,
    })
