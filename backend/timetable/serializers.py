# backend/timetable/serializers.py
from rest_framework import serializers
from .models import TimeTable

class TimeTableSessionSerializer(serializers.ModelSerializer):
    """
    Minimal serializer used by Allocation views to list sessions.
    Maps the model's primary key to `session_id` (as expected by the frontend),
    exposes campus as string, computes duration (minutes) if possible,
    and includes assigned staff names from Allocation.related_name="allocations".
    """
    session_id = serializers.IntegerField(source="timetable_id", read_only=True)
    campus = serializers.StringRelatedField()
    duration = serializers.SerializerMethodField()
    staff = serializers.SerializerMethodField()

    class Meta:
        model = TimeTable
        fields = [
            "session_id",
            "activity_code",
            "campus",
            "day_of_week",
            "start_time",
            "duration",       # computed (minutes) from start/end if available
            "location",
            "weeks",
            "staff",          # list of assigned tutor names/emails
        ]

    def get_duration(self, obj):
        # Prefer a model property if present (e.g., duration_minutes); else compute from start/end.
        # Safe fallbacks so the API never explodes.
        minutes = getattr(obj, "duration_minutes", None)
        if minutes is not None:
            try:
                return int(minutes)
            except Exception:
                pass
        # Attempt to compute from start_time/end_time if both exist
        try:
            from datetime import datetime, date
            if getattr(obj, "start_time", None) and getattr(obj, "end_time", None):
                start_dt = datetime.combine(date.today(), obj.start_time)
                end_dt = datetime.combine(date.today(), obj.end_time)
                return int((end_dt - start_dt).total_seconds() // 60)
        except Exception:
            pass
        # Final fallback
        return None

    def get_staff(self, obj):
        # Allocation.related_name="allocations"
        names = []
        for alloc in getattr(obj, "allocations", []).all():
            tutor = getattr(alloc, "tutor", None)
            if tutor:
                # Prefer full name if available, else email/username
                full = ""
                try:
                    full = tutor.get_full_name()
                except Exception:
                    pass
                names.append(full or getattr(tutor, "email", None) or getattr(tutor, "username", None) or "Unknown")
        return names
