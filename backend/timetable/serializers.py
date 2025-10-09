# backend/timetable/serializers.py
from rest_framework import serializers
from .models import TimeTable

DAY_MAP = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}

class TimeTableSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField(source="timetable_id", read_only=True)
    campus = serializers.SerializerMethodField()
    activity_code = serializers.SerializerMethodField()
    weeks = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    staff = serializers.SerializerMethodField()
    day_of_week = serializers.SerializerMethodField()
    location = serializers.CharField(source="room")

    class Meta:
        model = TimeTable
        fields = [
            "session_id",
            "activity_code",
            "day_of_week",
            "start_time",
            "duration",
            "location",
            "weeks",
            "campus",
            "staff",
        ]

    def get_campus(self, obj):
        try:
            return obj.campus.campus_name if obj.campus else ""
        except Exception:
            return ""

    def get_activity_code(self, obj):
        return getattr(obj, "activity_code_ui", "") or ""

    def get_weeks(self, obj):
        return getattr(obj, "weeks_ui", "") or ""

    def get_duration(self, obj):
        minutes = getattr(obj, "duration_minutes", None)
        if minutes is not None:
            try:
                return int(minutes)
            except Exception:
                pass
        try:
            from datetime import datetime, date
            if obj.start_time and obj.end_time:
                s = datetime.combine(date.today(), obj.start_time)
                e = datetime.combine(date.today(), obj.end_time)
                return int((e - s).total_seconds() // 60)
        except Exception:
            pass
        return None

    def get_staff(self, obj):
        names = []
        t = getattr(obj, "tutor_user", None)
        if t:
            full = (getattr(t, "get_full_name", lambda: "")() or "").strip()
            names.append(full or getattr(t, "email", "") or getattr(t, "username", "") or "Unknown")
        # if you also expose Allocation via reverse relation, list them too (optional)
        return names

    def get_day_of_week(self, obj):
        d = getattr(obj, "day_of_week", "")
        return DAY_MAP.get(d, d)
