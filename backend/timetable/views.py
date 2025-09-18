# timetable/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from timetable.models import TimeTable

DAY_MAP = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}

@require_GET
def sessions_list(request):
    alias = request.GET.get("alias") or "current"
    unit_code = request.GET.get("unit_code")
    campus = request.GET.get("campus")  # NEW

    qs = (TimeTable.objects.using(alias)
          .select_related("unit_course__unit", "campus", "master_class"))

    if unit_code:
        qs = qs.filter(unit_course__unit__unit_code__iexact=unit_code)
    if campus:
        qs = qs.filter(campus__campus_name__iexact=campus)

    rows = []
    for t in qs:
        # duration (minutes)
        dur = 0
        if t.start_time and t.end_time:
            dur = (t.end_time.hour * 60 + t.end_time.minute) - (t.start_time.hour * 60 + t.start_time.minute)

        # weeks string
        weeks_str = ""
        if t.master_class:
            weeks_str = getattr(t.master_class, "weeks", "") or ""
            if not weeks_str:
                tw = getattr(t.master_class, "teaching_weeks", None)
                weeks_str = str(tw) if tw is not None else ""

        rows.append({
            "session_id":    getattr(t, "timetable_id", t.pk),
            "activity_code": getattr(getattr(t.unit_course, "unit", None), "unit_code", ""),
            "unit_name":     getattr(getattr(t.unit_course, "unit", None), "unit_name", ""),
            "campus":        getattr(getattr(t, "campus", None), "campus_name", "") or "",
            "day_of_week":   DAY_MAP.get(t.day_of_week, t.day_of_week),
            "start_time":    t.start_time.strftime("%H:%M") if t.start_time else "",
            "end_time":      t.end_time.strftime("%H:%M") if t.end_time else "",
            "duration":      dur,
            "location":      t.room or "",
            "weeks":         weeks_str,
            "notes":         t.notes or "",
            "tutor":         (t.tutor_user.get_full_name() if getattr(t, "tutor_user", None) else ""),
        })

    return JsonResponse(rows, safe=False)
