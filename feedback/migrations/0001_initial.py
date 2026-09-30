from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("message", models.TextField(max_length=1000)),
                ("image", models.ImageField(blank=True, upload_to="feedback/%Y/%m/")),
                (
                    "status",
                    models.CharField(
                        choices=[("new", "New"), ("reviewed", "Reviewed"), ("resolved", "Resolved")],
                        default="new",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "feedback",
                "ordering": ["-created_at"],
            },
        ),
    ]
