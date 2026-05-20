from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="ai_reason",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="document",
            name="ai_model",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="document",
            name="ai_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="ai_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="document",
            name="ai_last_error",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
    ]
