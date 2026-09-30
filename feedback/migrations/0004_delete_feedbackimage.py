from django.db import migrations


class Migration(migrations.Migration):
    """Remove the leftover FeedbackImage table.

    Migration 0003 created it, but the model no longer exists in models.py. If the table still holds
    rows, SQLite refuses to delete the feedback they point to, which makes deleting fail.
    """

    dependencies = [
        ("feedback", "0003_remove_feedback_user_alter_feedback_message_and_more"),
    ]

    operations = [
        migrations.DeleteModel(name="FeedbackImage"),
    ]
