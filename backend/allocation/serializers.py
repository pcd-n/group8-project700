#allocation/serializers.py
from rest_framework import serializers
from .models import Allocation

class AllocationSerializer(serializers.ModelSerializer):
    tutor_name = serializers.CharField(source="tutor.get_full_name", read_only=True)
    session_info = serializers.SerializerMethodField()

    class Meta:
        model = Allocation
        fields = [
            "id", "session", "session_info", "tutor", "tutor_name",
            "preference", "status", "approved", "created_at"
        ]
        read_only_fields = ["id", "created_at"]

    def get_session_info(self, obj):
        s = obj.session
        return {
            "id": s.id,
            "session_id": getattr(s, "pk", None),
            # try common names; fall back to None if not present
            "unit": getattr(getattr(s, "unit_course", None), "unit_id", None) or getattr(s, "unit_id", None),
            "day": getattr(s, "day_of_week", None) or getattr(s, "day", None),
            "start": str(getattr(s, "start_time", "")) or str(getattr(s, "start", "")),
            "end": str(getattr(s, "end_time", "")) or str(getattr(s, "finish", "")) or str(getattr(s, "end", "")),
            "room": getattr(s, "room", None),
            "campus_id": getattr(s, "campus_id", None),
        }

class ManualAssignSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    tutor_id = serializers.IntegerField()
    preference = serializers.IntegerField(required=False, default=0)

class AssignRequestSerializer(serializers.Serializer):
    session_id     = serializers.IntegerField()
    tutor_user_id  = serializers.IntegerField(required=False, allow_null=True)
    tutor_email    = serializers.EmailField(required=False, allow_blank=True)
    notes          = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # allow notes-only, but require at least one of tutor fields or notes to be present
        if not attrs.get("tutor_user_id") and not attrs.get("tutor_email") and "notes" not in attrs:
            raise serializers.ValidationError("Provide tutor_user_id, tutor_email, or notes.")
        return attrs