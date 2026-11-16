"""Проверка URL, шаблонов и SQL на отдельной временной базе ПР7."""

import json
from datetime import date

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from db import database
from db.import_json import import_all


@pytest.fixture
def client(tmp_path, monkeypatch):
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
    monkeypatch.setattr(database, "DB_PATH", db_path)
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
    assert [book["id"] for book in response.context["books"]] == expected


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
    assert {book["id"] for book in response.context["books"]} == expected


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
    assert {loan["id"] for loan in response.context["loans"]} == expected
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
    assert response.context["active_loan"]["id"] == 3
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
        "loans_count": 4, "issued_count": 2,
    }
    assert response.context["durations"]["avg_days"] == 9.5
    assert response.context["active_readers"][0]["name"] == "Иван"
    unused = next(book for book in response.context["popular_books"]
                  if book["id"] == 4)
    assert unused["loans_count"] == 0
    response = client.get(reverse("loans:statistics"), {"min": "invalid"})
    assert response.status_code == 200
    assert response.context["min_loans"] == 2


def test_empty_database_and_same_day_return(client):
    conn = database.get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM loans WHERE id != 4")
        response = client.get(reverse("loans:statistics"))
        assert response.context["durations"]["avg_days"] == 0
        assert "нет данных" not in response.content.decode()
        with conn:
            conn.execute("DELETE FROM loans")
            conn.execute("DELETE FROM readers")
            conn.execute("DELETE FROM books")
    finally:
        conn.close()
    for name in ("books:list", "books:available", "loans:list",
                 "loans:overdue", "loans:readers", "loans:statistics"):
        assert client.get(reverse(name)).status_code == 200
