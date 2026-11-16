"""Однократный перенос исторических записей из базы ПР7."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from books.models import Book
from db.database import DB_PATH
from loans.models import Loan, Reader


class Command(BaseCommand):
    help = "Перенести книги, читателей и выдачи из базы SQLite ПР7."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=DB_PATH)

    def handle(self, *args, **options):
        source = options["source"].resolve()
        try:
            with closing(sqlite3.connect(
                f"{source.as_uri()}?mode=ro", uri=True,
            )) as legacy, transaction.atomic():
                legacy.row_factory = sqlite3.Row
                legacy.execute("BEGIN")
                books = legacy.execute("SELECT id, title, author FROM books")
                readers = legacy.execute(
                    "SELECT id, name, ticket FROM readers",
                )
                loans = legacy.execute(
                    "SELECT id, book_id, reader_id, issue_date, "
                    "return_date "
                    "FROM loans"
                )
                book_count = self.transfer(Book, books)
                reader_count = self.transfer(Reader, readers)
                loan_count = self.transfer(Loan, loans)
        except (sqlite3.Error, ValueError, IntegrityError) as exc:
            raise CommandError(f"Ошибка переноса из {source}: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            f"Добавлено книг: {book_count}, читателей: {reader_count}, "
            f"выдач: {loan_count}."
        ))

    def transfer(self, model, rows):
        count = 0
        for row in rows:
            fields = dict(row)
            pk = fields.pop("id")
            if model is Loan:
                fields["issue_date"] = date.fromisoformat(fields["issue_date"])
                if fields["return_date"] is not None:
                    fields["return_date"] = date.fromisoformat(
                        fields["return_date"],
                    )
            obj, created = model.objects.get_or_create(pk=pk, defaults=fields)
            if not created and any(
                getattr(obj, key) != value for key, value in fields.items()
            ):
                raise CommandError(
                    f"Конфликт записи «{model._meta.verbose_name}» №{pk}. "
                    "Перенос отменён."
                )
            count += created
        return count
