"""Класс Reader и функции работы с читателями."""

from typing import Any, List, Optional

from utils import generate_id

from .base import LibraryObject


class Reader(LibraryObject):
    """Читатель библиотеки с читательским билетом."""

    def __init__(self, reader_id: int, name: str, ticket: str) -> None:
        super().__init__(reader_id)
        if (not isinstance(name, str) or not name.strip()
                or not isinstance(ticket, str) or not ticket.strip()):
            raise ValueError("Имя и номер билета не могут быть пустыми")
        self.name = name.strip()
        self.ticket = ticket.strip()

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "Reader":
        """Создать читателя из словаря, прочитанного из JSON."""
        return cls(data["id"], data["name"], data["ticket"])

    def to_data(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "ticket": self.ticket}

    def has_ticket(self, ticket: str) -> bool:
        """Проверить номер читательского билета без учёта регистра."""
        return self.ticket.casefold() == ticket.strip().casefold()

    def __str__(self) -> str:
        return f"{self.id:>3}. {self.name} (билет {self.ticket})"


def find_reader_by_ticket(
    readers: List[Reader],
    ticket: str,
) -> Optional[Reader]:
    """Найти читателя по номеру читательского билета."""
    for reader in readers:
        if reader.has_ticket(ticket):
            return reader
    return None


def find_reader_by_id(
    readers: List[Reader],
    reader_id: int,
) -> Optional[Reader]:
    """Найти читателя по идентификатору."""
    for reader in readers:
        if reader.id == reader_id:
            return reader
    return None


def add_reader(readers: List[Reader], name: str, ticket: str) -> Reader:
    """Создать читателя; номер билета должен быть уникальным."""
    if find_reader_by_ticket(readers, ticket) is not None:
        raise ValueError(f"Билет {ticket} уже зарегистрирован")
    reader = Reader(generate_id(r.id for r in readers), name, ticket)
    readers.append(reader)
    return reader


def show_readers(readers: List[Reader]) -> None:
    """Вывести список читателей."""
    for reader in readers:
        print(reader)
