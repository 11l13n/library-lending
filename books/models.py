"""Модель каталога библиотеки."""

from uuid import uuid4

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Casefold(models.Func):
    function = "casefold"
    output_field = models.TextField()


class Book(models.Model):
    title = models.TextField("название")
    author = models.TextField("автор")

    slug = models.SlugField("адрес", max_length=180, unique=True,
                            allow_unicode=True, editable=False)

    class Meta:
        verbose_name = "книга"
        verbose_name_plural = "книги"

    def __str__(self):
        return f"{self.title} — {self.author}"

    def get_absolute_url(self):
        return reverse("books:by-slug", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            title_slug = slugify(self.title, allow_unicode=True)[:145]
            suffix = self.pk if self.pk is not None else uuid4().hex
            self.slug = f"{title_slug or 'book'}-{suffix}"
        return super().save(*args, **kwargs)
