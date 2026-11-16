from django.urls import path, re_path

from . import views

app_name = "books"

urlpatterns = [
    path("", views.books, name="list"),
    path("search/", views.search, name="search"),
    path("available/", views.available, name="available"),
    path("<int:book_id>/", views.book_detail, name="detail"),
    re_path(r"^catalog/(?P<slug>[-\w]+)/$", views.book_detail, name="by-slug"),
]
