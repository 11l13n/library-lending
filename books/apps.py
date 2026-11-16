from django.apps import AppConfig
from django.db.backends.signals import connection_created

from db.database import casefold


def register_casefold(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.connection.create_function(
            "casefold", 1, casefold, deterministic=True,
        )


class BooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "books"

    def ready(self):
        connection_created.connect(register_casefold)
