"""Базовый класс объектов учёта библиотеки."""

from typing import Any


class LibraryObject:
    """Объект учёта: имеет идентификатор и сохраняется в JSON.

    Книга, читатель и выдача являются объектами учёта, поэтому
    наследуют общий идентификатор и интерфейс to_data().
    """

    def __init__(self, object_id: int) -> None:
        if type(object_id) is not int or object_id <= 0:
            raise ValueError("Идентификатор должен быть положительным")
        self.id = object_id

    def to_data(self) -> dict[str, Any]:
        """Преобразовать объект в словарь для записи в JSON."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id})"
