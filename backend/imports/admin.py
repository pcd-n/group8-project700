from django.contrib import admin
from .models import UploadJob

@admin.register(UploadJob)
class UploadJobAdmin(admin.ModelAdmin):
    list_display = ("id", "import_type", "ok", "rows_ok", "rows_error", "started_at", "finished_at")
    readonly_fields = [f.name for f in UploadJob._meta.fields]
