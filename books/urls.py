from django.urls import path

from . import views

app_name = "books"

urlpatterns = [
    path("", views.books, name="list"),
    path("search/", views.search, name="search"),
    path("available/", views.available, name="available"),
    path("<int:book_id>/", views.book_detail, name="detail"),
]
