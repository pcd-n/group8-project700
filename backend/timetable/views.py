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
    Returns timetable sessions for a semester alias, optionally filtered by unit_code and campus.
    Response items include: activity_code (unit code), unit_name, campus, day_of_week, start/end, duration, location, weeks, notes, tutor.
    """
    alias = request.GET.get("alias") or get_current_semester_alias()
    unit_code = request.GET.get("unit_code")
    campus = request.GET.get("campus")

    # IMPORTANT: switch DB via router context; DO NOT call .using(alias)
    with force_write_alias(alias):
        qs = (TimeTable.objects
              .select_related("unit_course__unit", "unit_course__campus", "tutor_user")
              .all())

        if unit_code:
            qs = qs.filter(unit_course__unit__unit_code__iexact=unit_code)

        if campus:
            qs = qs.filter(unit_course__campus__campus_name__iexact=campus)

        rows = []
        for t in qs:
            # duration in minutes (safe even if times are None)
            duration = 0
            if t.start_time and t.end_time:
                s = t.start_time.hour * 60 + t.start_time.minute
                e = t.end_time.hour * 60 + t.end_time.minute
                duration = max(0, e - s)

            # weeks string (support either weeks or teaching_weeks on master_class)
            weeks_str = ""
            if getattr(t, "master_class", None) is not None:
                weeks_str = getattr(t.master_class, "weeks", "") or ""
                if not weeks_str:
                    tw = getattr(t.master_class, "teaching_weeks", None)
                    weeks_str = str(tw) if tw is not None else ""

            unit = t.unit_course.unit if t.unit_course else None
            campus_name = t.unit_course.campus.campus_name if (t.unit_course and t.unit_course.campus) else ""

            rows.append({
                "session_id":   getattr(t, "timetable_id", t.pk),
                "activity_code": (unit.unit_code if unit else "")[:6].upper(),
                "unit_name":     unit.unit_name if unit else "",
                "campus":        campus_name,
                "day_of_week":   DAY_MAP.get(t.day_of_week, t.day_of_week),
                "start_time":    t.start_time.strftime("%H:%M") if t.start_time else "",
                "end_time":      t.end_time.strftime("%H:%M") if t.end_time else "",
                "duration":      duration,
                "location":      t.room or "",
                "weeks":         weeks_str,
                "notes": t.notes or "",
                "tutor": (t.tutor_user.get_full_name() if t.tutor_user else ""),
                "tutor_email": (t.tutor_user.email if t.tutor_user else ""),
            })

    return JsonResponse(rows, safe=False)