from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class UploadJob(models.Model):
    TYPE_CHOICES = [
        ("eoi", "EOI (Casual Master/EOI spreadsheet)"),
        ("master_classes", "Master Class List"),
        ("master_class_list", "Master Class List (alt key)"),
        ("tutorial_allocations", "Tutorial Allocations"),
    ]
    file = models.FileField(upload_to="uploads/")
    import_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    rows_total = models.PositiveIntegerField(default=0)
    rows_ok = models.PositiveIntegerField(default=0)
    rows_error = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.get_import_type_display()} @ {self.started_at:%Y-%m-%d %H:%M}"
