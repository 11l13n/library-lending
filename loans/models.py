"""Модели читателей и выдач."""

from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Cast, Coalesce, Greatest

from books.models import Book
from models.loans import FINE_PER_DAY, LOAN_PERIOD_DAYS, calculate_due_date

MICROSECONDS_PER_DAY = 86_400_000_000


def days_between(end, start):
    return models.ExpressionWrapper(
        Cast(end - start, models.BigIntegerField())
        / Value(MICROSECONDS_PER_DAY),
        output_field=models.IntegerField(),
    )


def overdue_days_expression(end, start):
    return Greatest(Value(0), days_between(end, start) - LOAN_PERIOD_DAYS)


class Reader(models.Model):
    name = models.TextField("имя")
    ticket = models.TextField("читательский билет", unique=True)

    class Meta:
        verbose_name = "читатель"
        verbose_name_plural = "читатели"

    def __str__(self):
        return f"{self.name} ({self.ticket})"


class LoanStatus(models.TextChoices):
    ACTIVE = "active", "У читателя"
    COMPLETED = "completed", "Возвращена"
    CANCELLED = "cancelled", "Отменена"


class LoanQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=LoanStatus.ACTIVE)

    def completed(self):
        return self.filter(status=LoanStatus.COMPLETED)

    def cancelled(self):
        return self.filter(status=LoanStatus.CANCELLED)

    def blocking_on(self, day):
        return self.filter(
            Q(status=LoanStatus.ACTIVE)
            | Q(status=LoanStatus.COMPLETED, return_date__gt=day),
            issue_date__lte=day,
        )

    def with_people_and_books(self):
        return self.select_related("book", "reader")

    def with_penalty(self, day):
        return self.annotate(
            overdue_days=models.Case(
                models.When(status=LoanStatus.CANCELLED, then=Value(0)),
                default=overdue_days_expression(
                    Coalesce("return_date", Value(day)), F("issue_date"),
                ),
            ),
            fine=F("overdue_days") * int(FINE_PER_DAY),
        )


class Loan(models.Model):
    Status = LoanStatus
    objects = LoanQuerySet.as_manager()

    book = models.ForeignKey(
        Book, on_delete=models.PROTECT, related_name="loans",
        verbose_name="книга",
    )
    reader = models.ForeignKey(
        Reader, on_delete=models.PROTECT, related_name="loans",
        verbose_name="читатель",
    )
    issue_date = models.DateField("дата выдачи")
    return_date = models.DateField("дата возврата", null=True, blank=True)
    status = models.CharField(
        "статус", max_length=9, choices=Status.choices, default=Status.ACTIVE,
    )

    class Meta:
        verbose_name = "выдача"
        verbose_name_plural = "выдачи"
        constraints = [
            models.CheckConstraint(
                condition=Q(return_date__isnull=True)
                | Q(return_date__gte=F("issue_date")),
                name="loan_return_on_or_after_issue",
            ),
            models.CheckConstraint(
                condition=Q(status="completed", return_date__isnull=False)
                | Q(status__in=["active", "cancelled"],
                    return_date__isnull=True),
                name="loan_status_matches_return",
            ),
            models.UniqueConstraint(
                fields=["book"], condition=Q(status="active"),
                name="loan_unique_active_book",
            ),
        ]

    @property
    def due_date(self):
        return calculate_due_date(self.issue_date)

    def __str__(self):
        return f"Выдача №{self.pk} — {self.book}"
