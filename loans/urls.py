from django.urls import path

from . import views

app_name = "loans"

urlpatterns = [
    path("", views.loans, name="list"),
    path("overdue/", views.overdue, name="overdue"),
    path("readers/", views.readers, name="readers"),
    path("statistics/", views.statistics, name="statistics"),
    path("<int:loan_id>/", views.loan_detail, name="detail"),
]
