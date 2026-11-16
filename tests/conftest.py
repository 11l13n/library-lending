"""Настройка Django для pytest без доступа к рабочим базам данных."""

import os

import django
from django.test.utils import setup_test_environment, teardown_test_environment


def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library.settings")
    django.setup()
    setup_test_environment()


def pytest_unconfigure():
    teardown_test_environment()
