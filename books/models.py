"""Модель каталога библиотеки."""

from django.db import models


class Casefold(models.Func):
    function = "casefold"
    output_field = models.TextField()


class Book(models.Model):
    title = models.TextField("название")
    author = models.TextField("автор")

    class Meta:
        verbose_name = "книга"
        verbose_name_plural = "книги"

    def __str__(self):
        return f"{self.title} — {self.author}"
