from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    book_model = apps.get_model("books", "Book")
    for book in book_model.objects.using(schema_editor.connection.alias).all():
        title_slug = slugify(book.title, allow_unicode=True)[:145]
        book.slug = f"{title_slug or 'book'}-{book.pk}"
        book.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [("books", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="book",
            name="slug",
            field=models.SlugField(
                "адрес", max_length=180, allow_unicode=True, null=True,
                editable=False,
            ),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="book",
            name="slug",
            field=models.SlugField(
                "адрес", max_length=180, allow_unicode=True, unique=True,
                editable=False,
            ),
        ),
    ]
