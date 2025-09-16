from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("eoi", "0002_eoiapp_availability_eoiapp_preference_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="eoiapp",
            name="tutor_email",
            field=models.EmailField(max_length=254, null=True, blank=True, db_index=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="tutor_name",
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="tutor_current",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="location_text",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="gpa",
            field=models.DecimalField(null=True, blank=True, max_digits=4, decimal_places=2),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="supervisor",
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="applied_units",
            field=models.JSONField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="tutoring_experience",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="hours_available",
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="scholarship_received",
            field=models.BooleanField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="transcript_link",
            field=models.URLField(max_length=500, blank=True),
        ),
        migrations.AddField(
            model_name="eoiapp",
            name="cv_link",
            field=models.URLField(max_length=500, blank=True),
        ),
    ]
