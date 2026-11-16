from django.contrib import admin

from loans.admin import LoanHistoryInline

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "id")
    search_fields = ("title", "author")
    list_filter = ("author",)
    readonly_fields = ("slug",)
    ordering = ("title", "id")
    inlines = (LoanHistoryInline,)
