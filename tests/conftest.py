"""Настройка Django для pytest без доступа к рабочим базам данных."""

import os

import django
import pytest
from django.db import transaction
from django.test.utils import (
    setup_databases, setup_test_environment,
    teardown_databases, teardown_test_environment,
)


def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library.settings")
    django.setup()
    setup_test_environment()


def pytest_unconfigure():
    teardown_test_environment()


@pytest.fixture(scope="session")
def django_test_db():
    config = setup_databases(verbosity=0, interactive=False)
    try:
        yield
    finally:
        teardown_databases(config, verbosity=0)


@pytest.fixture
def orm_db(django_test_db):
    with transaction.atomic():
        yield
        transaction.set_rollback(True)
