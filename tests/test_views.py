"""Проверка URL, шаблонов и ORM на временной базе Django."""

import json
from datetime import date

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

from books.models import Book
from db.import_json import import_all
from loans.models import Loan, Reader


@pytest.fixture
def client(tmp_path, monkeypatch, orm_db):
    records = {
        "books": [
            {"id": 1, "title": "Мастер и Маргарита", "author": "Булгаков"},
            {"id": 2, "title": "Евгений Онегин", "author": "Пушкин"},
            {"id": 3, "title": "Капитанская дочка", "author": "Пушкин"},
            {"id": 4, "title": "Без выдач", "author": "Автор"},
        ],
        "readers": [
            {"id": 1, "name": "Иван", "ticket": "Б-1"},
            {"id": 2, "name": "Анна", "ticket": "Б-2"},
            {"id": 3, "name": "Без выдач", "ticket": "Б-3"},
        ],
        "loans": [
            {"id": 1, "book_id": 1, "reader_id": 1,
             "issue_date": "2026-09-01", "return_date": "2026-09-20"},
            {"id": 2, "book_id": 2, "reader_id": 1,
             "issue_date": "2026-09-10", "return_date": None},
            {"id": 3, "book_id": 1, "reader_id": 2,
             "issue_date": "2026-10-01", "return_date": None},
            {"id": 4, "book_id": 3, "reader_id": 1,
             "issue_date": "2026-09-05", "return_date": "2026-09-05"},
        ],
    }
    for name, rows in records.items():
        (tmp_path / f"{name}.json").write_text(
            json.dumps(rows), encoding="utf-8",
        )
    db_path = tmp_path / "library.sqlite"
    import_all(db_path, *(tmp_path / f"{name}.json" for name in records))
    call_command("import_pr7", source=db_path)
    monkeypatch.setattr("django.utils.timezone.localdate",
                        lambda: date(2026, 10, 20))
    with override_settings(ALLOWED_HOSTS=["testserver"]):
        yield Client()


@pytest.mark.parametrize("name,kwargs,template", [
    ("homepage:index", {}, "homepage/index.html"),
    ("books:list", {}, "books/book_list.html"),
    ("books:search", {}, "books/search.html"),
    ("books:available", {}, "books/available.html"),
    ("books:detail", {"book_id": 1}, "books/book_detail.html"),
    ("loans:list", {}, "loans/loan_list.html"),
    ("loans:overdue", {}, "loans/overdue.html"),
    ("loans:readers", {}, "loans/readers.html"),
    ("loans:statistics", {}, "loans/statistics.html"),
    ("loans:detail", {"loan_id": 1}, "loans/loan_detail.html"),
])
def test_pages_render_with_base_template(client, name, kwargs, template):
    response = client.get(reverse(name, kwargs=kwargs))
    assert response.status_code == 200
    templates = {item.name for item in response.templates}
    assert {template, "base.html", "includes/navigation.html"} <= templates


def test_catalog_keeps_books_without_loans(client):
    response = client.get(reverse("books:list"))
    assert len(response.context["books"]) == 4
    assert response.context["issued_count"] == 2


@pytest.mark.parametrize("query,expected", [
    ("пУшКиН", [2, 3]), ("МАСТЕР", [1]), ("' OR 1=1 --", []),
    ("   ", []),
])
def test_search_uses_parameters_and_cyrillic_casefold(client, query, expected):
    response = client.get(reverse("books:search"), {"q": query})
    assert [book.pk for book in response.context["books"]] == expected


@pytest.mark.parametrize("value,expected", [
    ("2026-08-31", {1, 2, 3, 4}),
    ("2026-09-01", {2, 3, 4}),
    ("2026-09-19", {3, 4}),
    ("2026-09-20", {1, 3, 4}),
    ("2026-10-01", {3, 4}),
    ("invalid", {3, 4}),
])
def test_available_books_on_date(client, value, expected):
    response = client.get(reverse("books:available"), {"date": value})
    assert response.status_code == 200
    assert {book.pk for book in response.context["books"]} == expected


@pytest.mark.parametrize("value,expected,fine", [
    ("2026-09-15", set(), 0),
    ("2026-09-16", {1}, 10),
    ("2026-09-19", {1}, 40),
    ("2026-09-20", set(), 0),
    ("2026-09-25", {2}, 10),
])
def test_overdue_uses_history_and_due_date_boundary(
    client, value, expected, fine,
):
    response = client.get(reverse("loans:overdue"), {"date": value})
    assert {loan.pk for loan in response.context["loans"]} == expected
    assert response.context["total_fine"] == fine


def test_invalid_date_uses_local_today(client):
    for name in ("books:available", "loans:overdue"):
        response = client.get(reverse(name), {"date": "2026-02-30"})
        assert response.context["check_date"] == date(2026, 10, 20)


@pytest.mark.parametrize("name,kwargs", [
    ("books:detail", {"book_id": 999}),
    ("loans:detail", {"loan_id": 999}),
])
def test_missing_object_returns_404(client, name, kwargs):
    assert client.get(reverse(name, kwargs=kwargs)).status_code == 404


def test_custom_404_handler(client):
    with override_settings(DEBUG=False):
        response = client.get("/does-not-exist/")
    assert response.status_code == 404
    assert "homepage/404.html" in {item.name for item in response.templates}


def test_book_history_and_reader_totals(client):
    response = client.get(reverse("books:detail", kwargs={"book_id": 1}))
    assert len(response.context["history"]) == 2
    assert response.context["active_loan"].pk == 3
    response = client.get(reverse("loans:readers"))
    readers = {reader["id"]: reader for reader in response.context["readers"]}
    assert readers[1]["loans_count"] == 3
    assert readers[1]["on_hands"] == 1
    assert readers[1]["fine"] == 310
    assert readers[3]["loans_count"] == readers[3]["fine"] == 0


def test_statistics_uses_aggregates_and_having(client):
    response = client.get(reverse("loans:statistics"), {"min": 2})
    assert dict(response.context["summary"]) == {
        "books_count": 4, "readers_count": 3,
        "loans_count": 4, "issued_count": 2, "completed_count": 2,
        "cancelled_count": 0,
    }
    assert response.context["durations"]["avg_days"] == 9.5
    assert response.context["active_readers"][0]["name"] == "Иван"
    unused = next(book for book in response.context["popular_books"]
                  if book.pk == 4)
    assert unused.loans_count == 0
    response = client.get(reverse("loans:statistics"), {"min": "invalid"})
    assert response.status_code == 200
    assert response.context["min_loans"] == 2


def test_empty_database_and_same_day_return(client):
    Loan.objects.exclude(pk=4).delete()
    response = client.get(reverse("loans:statistics"))
    assert response.context["durations"]["avg_days"] == 0
    assert "нет данных" not in response.content.decode()
    Loan.objects.all().delete()
    Reader.objects.all().delete()
    Book.objects.all().delete()
    for name in ("books:list", "books:available", "loans:list",
                 "loans:overdue", "loans:readers", "loans:statistics"):
        assert client.get(reverse(name)).status_code == 200


def test_loan_filters_sort_and_pagination(client):
    for number in range(10):
        book = Book.objects.create(title=f"Мастер {number}", author="Автор")
        Loan.objects.create(
            book=book, reader_id=2, issue_date=date(2026, 10, 1),
        )
    filters = {
        "book": "МАСТЕР", "reader": "анНА", "date": "2026-10-01",
        "sort": "newest",
    }
    response = client.get(reverse("loans:list"), filters)
    page = response.context["page_obj"]
    assert page.paginator.count == 11
    assert len(page.object_list) == 10
    assert "sort=newest&amp;page=2" in response.content.decode()
    response = client.get(reverse("loans:list"), {**filters, "page": 2})
    assert [loan.pk for loan in response.context["loans"]] == [3]


def test_cancelled_loan_frees_book_without_changing_historical_returns(client):
    Loan.objects.filter(pk=3).update(status=Loan.Status.CANCELLED)
    response = client.get(reverse("books:available"), {"date": "2026-10-01"})
    assert 1 in {book.pk for book in response.context["books"]}
    response = client.get(reverse("books:available"), {"date": "2026-09-19"})
    assert 1 not in {book.pk for book in response.context["books"]}
    response = client.get(reverse("loans:list"), {"status": "cancelled"})
    assert [loan.pk for loan in response.context["loans"]] == [3]
    response = client.get(reverse("loans:statistics"))
    assert response.context["summary"]["cancelled_count"] == 1


def test_unicode_book_url_and_legacy_id(client):
    book = Book.objects.get(pk=1)
    assert client.get(book.get_absolute_url()).context["book"] == book
    assert client.get(reverse("books:detail", args=[1])).status_code == 200
    missing_url = reverse("books:by-slug", args=["missing"])
    assert client.get(missing_url).status_code == 404


def test_loan_filter_displays_invalid_date(client):
    response = client.get(reverse("loans:list"), {"date": "2026-02-30"})
    assert response.context["form"].has_error("date", "invalid")
    assert not response.context["loans"]


@pytest.mark.parametrize("invalid_date", [
    "", "2026-02-30", "2026-10-19", "9999-12-31",
])
def test_loan_form_rejects_invalid_date(client, invalid_date):
    before = Loan.objects.count()
    response = client.post(reverse("loans:create"), {
        "book": 4, "reader": 1, "issue_date": invalid_date,
    })
    assert response.status_code == 200
    assert "issue_date" in response.context["form"].errors
    assert Loan.objects.count() == before


def test_loan_form_rejects_occupied_book_and_missing_fields(client):
    url = reverse("loans:create")
    payload = {"book": 2, "reader": 1, "issue_date": "2026-10-20"}
    response = client.post(url, payload)
    assert "book" in response.context["form"].errors
    response = client.post(url, {**payload, "book": 4, "reader": ""})
    assert response.context["form"].has_error("reader", "required")
    assert not Loan.objects.filter(book_id=4).exists()


def test_loan_creation_edit_cancellation_and_book_reuse(client):
    create_url = reverse("loans:create")
    payload = {"book": 4, "reader": 1, "issue_date": "2026-10-20"}
    assert client.get(create_url).status_code == 200
    response = client.post(create_url, payload)
    loan = Loan.objects.get(book_id=4)
    detail_url = reverse("loans:detail", args=[loan.pk])
    assert response.url == detail_url
    assert loan.status == Loan.Status.ACTIVE
    edit_url = reverse("loans:edit", args=[loan.pk])
    assert client.get(edit_url).context["form"].instance == loan
    response = client.post(edit_url, {**payload, "reader": 2})
    assert response.url == detail_url
    loan.refresh_from_db()
    assert loan.reader_id == 2
    assert client.post(
        edit_url, {**payload, "book": 2},
    ).context["form"].has_error("book")
    cancel_url = reverse("loans:cancel", args=[loan.pk])
    assert client.get(cancel_url).status_code == 405
    assert Loan.objects.active().filter(pk=loan.pk).exists()
    assert client.post(cancel_url).url == detail_url
    assert client.post(cancel_url).url == detail_url
    assert Loan.objects.cancelled().filter(pk=loan.pk).exists()
    assert client.get(edit_url).status_code == 404
    assert client.post(create_url, payload).status_code == 302
    assert Loan.objects.active().filter(book_id=4).count() == 1


def test_edit_keeps_original_past_date_and_rejects_past_change(client):
    url = reverse("loans:edit", args=[2])
    payload = {"book": 2, "reader": 2, "issue_date": "2026-09-10"}
    assert client.post(url, payload).status_code == 302
    response = client.post(url, {**payload, "issue_date": "2026-09-11"})
    assert response.context["form"].has_error("issue_date")
    assert Loan.objects.get(pk=2).issue_date == date(2026, 9, 10)


def test_loan_post_requires_csrf_token(client):
    secured = Client(enforce_csrf_checks=True)
    create_url = reverse("loans:create")
    cancel_url = reverse("loans:cancel", args=[2])
    assert secured.post(create_url).status_code == 403
    assert secured.post(cancel_url).status_code == 403
    assert Loan.objects.active().filter(pk=2).exists()
    detail_url = reverse("loans:detail", args=[2])
    assert secured.get(detail_url).status_code == 200
    token = secured.cookies["csrftoken"].value
    assert secured.post(
        cancel_url, {"csrfmiddlewaretoken": token},
    ).status_code == 302


def test_missing_loan_edit_and_cancel_return_404(client):
    assert client.get(reverse("loans:edit", args=[999])).status_code == 404
    assert client.post(reverse("loans:cancel", args=[999])).status_code == 404
