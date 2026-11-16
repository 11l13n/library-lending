import pytest

from models import Reader
from models.readers import add_reader, find_reader_by_id, find_reader_by_ticket


def test_reader_from_data():
    reader = Reader.from_data({"id": 1, "name": "Иван", "ticket": "Б-1"})
    assert reader.name == "Иван"
    assert str(reader) == "  1. Иван (билет Б-1)"


def test_add_and_find_reader():
    readers = []
    reader = add_reader(readers, "Иван Петров", "Б-0042")
    assert find_reader_by_ticket(readers, "б-0042") is reader
    assert find_reader_by_id(readers, 1) is reader


def test_duplicate_ticket_is_forbidden():
    readers = []
    add_reader(readers, "Иван Петров", "Б-0042")
    with pytest.raises(ValueError):
        add_reader(readers, "Анна Смирнова", "Б-0042")
