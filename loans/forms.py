from django import forms
from django.db.models import F, Q
from django.utils import timezone

from books.models import Book

from .models import Loan, Reader

LOAN_SORTS = {
    "oldest": ("Сначала ранние", ("issue_date", "id")),
    "newest": ("Сначала новые", ("-issue_date", "-id")),
    "book": ("По книге", ("book__title", "id")),
    "reader": ("По читателю", ("reader__name", "id")),
}
DATE_WIDGET = forms.DateInput(
    format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"},
)


class LoanFilterForm(forms.Form):
    date = forms.DateField(
        label="Дата выдачи", required=False, widget=DATE_WIDGET,
        input_formats=["%Y-%m-%d"],
    )
    book = forms.CharField(
        label="Книга", required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    reader = forms.CharField(
        label="Читатель или билет", required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    sort = forms.ChoiceField(
        label="Сортировка", required=False, initial="oldest",
        choices=[(key, label) for key, (label, _) in LOAN_SORTS.items()],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        label="Статус", required=False, initial=Loan.Status.ACTIVE,
        choices=[*Loan.Status.choices, ("all", "Все")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ("book", "reader", "issue_date")
        widgets = {
            "book": forms.Select(attrs={"class": "form-select"}),
            "reader": forms.Select(attrs={"class": "form-select"}),
            "issue_date": DATE_WIDGET,
        }
        help_texts = {"issue_date": "Срок возврата — 14 дней после выдачи."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book"].queryset = Book.objects.order_by(
            "title", "author", "pk",
        )
        self.fields["reader"].queryset = Reader.objects.order_by("name", "pk")
        self.fields["issue_date"].input_formats = ["%Y-%m-%d"]

    def clean_issue_date(self):
        issue_date = self.cleaned_data["issue_date"]
        if (issue_date < timezone.localdate()
                and issue_date != self.instance.issue_date):
            raise forms.ValidationError(
                "Укажите сегодняшний день или будущую дату.",
            )
        return issue_date

    def clean(self):
        data = super().clean()
        book = data.get("book")
        issue_date = data.get("issue_date")
        if book and issue_date:
            conflicts = book.loans.filter(
                Q(status=Loan.Status.ACTIVE)
                | (Q(status=Loan.Status.COMPLETED,
                     return_date__gt=issue_date)
                   & Q(return_date__gt=F("issue_date"))),
            ).exclude(pk=self.instance.pk)
            if conflicts.exists():
                self.add_error("book", "Книга уже выдана на выбранный период.")
        return data
