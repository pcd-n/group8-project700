# timetable/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from timetable.models import TimeTable
from semesters.threadlocal import force_write_alias
from semesters.router import get_current_semester_alias

DAY_MAP = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}

@require_GET
def sessions_list(request):
    """
    Return timetable sessions for alias, optionally filtered by unit_code & campus.
    Output fields are tailored for:
      - allocationdetails.html
      - tutortimetable.html
    """
    alias = request.GET.get("alias") or get_current_semester_alias()
    unit_code = request.GET.get("unit_code")
    campus = request.GET.get("campus")

    with force_write_alias(alias):
        qs = TimeTable.objects.select_related(
            "unit_course__unit", "campus", "tutor_user", "master_class"
        )

        if unit_code:
            qs = qs.filter(unit_course__unit__unit_code__iexact=unit_code)
        if campus:
            qs = qs.filter(campus__campus_name__iexact=campus)

        rows = []
        for t in qs:
            # duration (minutes)
            dur = None
            try:
                dur = int(getattr(t, "duration_minutes", None) or 0)
            except Exception:
                dur = 0

            unit = t.unit_course.unit if t.unit_course else None
            campus_name = t.campus.campus_name if t.campus else ""

            # Safe 'notes' (older DBs might lack column)
            try:
                notes_val = t.notes or ""
            except Exception:
                notes_val = ""

            tutor_name = ""
            tutor_email = ""
            try:
                if t.tutor_user:
                    tutor_name = t.tutor_user.get_full_name() or ""
                    tutor_email = t.tutor_user.email or ""
            except Exception:
                pass

            # Day label
            day_label = DAY_MAP.get(t.day_of_week, t.day_of_week)

            rows.append({
                "session_id":   getattr(t, "timetable_id", t.pk),
                "activity_code": getattr(t, "activity_code_ui", "") or "",
                "unit_name":     unit.unit_name if unit else "",
                "campus":        campus_name,
                "day_of_week":   day_label,
                "start_time":    t.start_time.strftime("%H:%M") if t.start_time else "",
                "end_time":      t.end_time.strftime("%H:%M") if t.end_time else "",
                "duration":      dur if dur is not None else 0,
                "location":      t.room or "",
                "weeks":         getattr(t, "weeks_ui", "") or "",
                "notes":         notes_val,
                "tutor":         tutor_name,
                "tutor_email":   tutor_email,
                "tutor_user_id": getattr(t, "tutor_user_id", None),
            })

    return JsonResponse(rows, safe=False)