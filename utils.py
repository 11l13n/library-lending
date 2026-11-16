"""Вспомогательные функции: идентификаторы и безопасный ввод."""

from datetime import date, datetime
from typing import Iterable

DATE_FORMAT = "%d.%m.%Y"


def generate_id(existing_ids: Iterable[int]) -> int:
    """Вернуть идентификатор, следующий за максимальным из существующих."""
    return max(existing_ids, default=0) + 1


def parse_date(text: str) -> date:
    """Преобразовать строку вида ДД.ММ.ГГГГ в дату.

    Возбуждает ValueError, если строка имеет неверный формат.
    """
    return datetime.strptime(text.strip(), DATE_FORMAT).date()


def format_date(value: date) -> str:
    """Преобразовать дату в строку вида ДД.ММ.ГГГГ."""
    return value.strftime(DATE_FORMAT)


def parse_iso_date(value: str | None, default: date) -> date:
    """Прочитать дату из GET-параметра или вернуть дату по умолчанию."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def input_int(prompt: str) -> int:
    """Запросить целое число; при ошибке ввода повторить запрос."""
    while True:
        text = input(prompt)
        try:
            return int(text)
        except ValueError:
            print("Ошибка: введите целое число.")


def input_date(prompt: str) -> date:
    """Запросить дату; пустой ввод означает сегодняшнюю дату."""
    while True:
        text = input(f"{prompt} (ДД.ММ.ГГГГ, Enter - сегодня): ")
        if not text.strip():
            return date.today()
        try:
            return parse_date(text)
        except ValueError:
            print("Ошибка: дата должна быть в формате ДД.ММ.ГГГГ.")


def input_text(prompt: str) -> str:
    """Запросить непустую строку."""
    while True:
        text = input(prompt).strip()
        if text:
            return text
        print("Ошибка: значение не может быть пустым.")
