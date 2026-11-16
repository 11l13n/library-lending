"""Модели читателей и выдач."""

from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Cast, Greatest

from books.models import Book
from models.loans import LOAN_PERIOD_DAYS, calculate_due_date

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


class Loan(models.Model):
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

    class Meta:
        verbose_name = "выдача"
        verbose_name_plural = "выдачи"
        constraints = [
            models.CheckConstraint(
                condition=Q(return_date__isnull=True)
                | Q(return_date__gte=F("issue_date")),
                name="loan_return_on_or_after_issue",
            ),
        ]

    @property
    def due_date(self):
        return calculate_due_date(self.issue_date)

    def __str__(self):
        return f"Выдача №{self.pk} — {self.book}"
