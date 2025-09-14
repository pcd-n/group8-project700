from rest_framework import serializers
from .models import Semester

class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ["alias", "db_name", "year", "term", "is_current", "created_at"]

class CreateSemesterSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    term = serializers.ChoiceField(choices=[("S1","S1"),("S2","S2"),("S3","S3"),("S4","S4")])
    make_current = serializers.BooleanField(default=True)

class SelectViewSerializer(serializers.Serializer):
    alias = serializers.CharField(allow_null=True, allow_blank=True, required=False)
