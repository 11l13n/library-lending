"""Страницы выдач, читателей и статистики."""

from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce, Round, TruncMonth
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from books.models import Book, Casefold
from models.loans import FINE_PER_DAY
from utils import parse_iso_date

from .forms import LOAN_SORTS, LoanFilterForm, LoanForm
from .models import Loan, Reader, days_between, overdue_days_expression


def loans(request):
    form = LoanFilterForm(request.GET or None)
    queryset = Loan.objects.with_people_and_books()
    filters = form.cleaned_data if form.is_valid() else {}
    status = filters.get("status") or Loan.Status.ACTIVE
    if status == Loan.Status.COMPLETED:
        queryset = queryset.completed()
    elif status == Loan.Status.CANCELLED:
        queryset = queryset.cancelled()
    elif status != "all":
        queryset = queryset.active()

    issue_date = filters.get("date")
    book = filters.get("book")
    reader = filters.get("reader")
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
    if form.errors:
        queryset = queryset.none()

    sort = filters.get("sort") or "oldest"
    page = Paginator(queryset.order_by(*LOAN_SORTS[sort][1]), 10).get_page(
        request.GET.get("page"),
    )
    return render(request, "loans/loan_list.html", {
        "loans": page.object_list, "page_obj": page, "form": form,
    })


@require_http_methods(["GET", "POST"])
def loan_form(request, loan_id=None):
    loan = None
    if loan_id is not None:
        loan = get_object_or_404(Loan.objects.active(), pk=loan_id)
    data = request.POST if request.method == "POST" else None
    form = LoanForm(data, instance=loan, initial={
        "issue_date": loan.issue_date if loan else timezone.localdate(),
    })
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        try:
            with transaction.atomic():
                if loan_id is None:
                    updated.save()
                else:
                    saved = Loan.objects.active().filter(pk=loan_id).update(
                        book=updated.book, reader=updated.reader,
                        issue_date=updated.issue_date,
                    )
                    if not saved:
                        raise Http404("Активная выдача не найдена.")
        except IntegrityError:
            conflicts = Loan.objects.active().filter(book=updated.book)
            if not conflicts.exclude(pk=loan_id).exists():
                raise
            form.add_error("book", "Книга уже выдана на выбранный период.")
        else:
            return redirect("loans:detail", loan_id=updated.pk)
    return render(request, "loans/loan_form.html", {
        "form": form, "loan_id": loan_id,
    })


@require_POST
def cancel_loan(request, loan_id):
    loan = get_object_or_404(Loan, pk=loan_id)
    Loan.objects.active().filter(pk=loan.pk).update(
        status=Loan.Status.CANCELLED,
    )
    return redirect("loans:detail", loan_id=loan.pk)


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
