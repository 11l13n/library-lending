from django.contrib import admin

from .models import Loan, Reader


class LoanHistoryInline(admin.TabularInline):
    model = Loan
    fields = ("book", "reader", "issue_date", "return_date", "status")
    readonly_fields = fields
    extra = 0
    show_change_link = True
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).with_people_and_books()

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Reader)
class ReaderAdmin(admin.ModelAdmin):
    list_display = ("name", "ticket")
    search_fields = ("name", "ticket")
    ordering = ("name", "id")
    inlines = (LoanHistoryInline,)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        "id", "book", "reader", "issue_date", "return_date", "status",
    )
    list_select_related = ("book", "reader")
    list_filter = ("status", "issue_date", "return_date")
    search_fields = ("book__title", "reader__name", "reader__ticket")
    ordering = ("-issue_date", "-id")
    date_hierarchy = "issue_date"
