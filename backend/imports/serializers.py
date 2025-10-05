# backend/imports/serializers.py
from rest_framework import serializers
from .models import UploadJob

class UploadJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadJob
        fields = ["id", "import_type", "file", "started_at", "finished_at",
                  "ok", "rows_total", "rows_ok", "rows_error", "log"]
        read_only_fields = ["id", "started_at", "finished_at", "ok",
                            "rows_total", "rows_ok", "rows_error", "log"]

class UploadRequestSerializer(serializers.Serializer):
    import_type = serializers.ChoiceField(choices=[c[0] for c in UploadJob.TYPE_CHOICES])
    file = serializers.FileField()
