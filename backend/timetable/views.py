# timetable/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from timetable.models import TimeTable
from semesters.threadlocal import force_write_alias
from semesters.router import get_current_semester_alias
from django.core.mail import EmailMessage
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.authentication import JWTAuthentication

DAY_MAP = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}

@require_GET
def sessions_list(request):
    """
    Return timetable sessions for alias, optionally filtered by unit_code & campus.
    Safe across old semester DBs that don't have 'notes' yet.
    """
    alias       = request.GET.get("alias") or get_current_semester_alias()
    unit_code   = request.GET.get("unit_code")
    campus      = request.GET.get("campus")
    tutor_email = request.GET.get("tutor_email") or request.GET.get("email")
    tutor_id    = request.GET.get("tutor_id")

    with force_write_alias(alias):
        qs = TimeTable.objects.using(alias).select_related(
             "unit_course__unit", "campus", "tutor_user", "master_class"
        )

        if unit_code:
            qs = qs.filter(unit_course__unit__unit_code__iexact=unit_code)
        if campus:
            qs = qs.filter(campus__campus_name__iexact=campus)
        if tutor_email:
            qs = qs.filter(tutor_user__email__iexact=tutor_email)
        if tutor_id:
            qs = qs.filter(tutor_user_id=tutor_id)
        rows = []
        for t in qs:
            # duration
            dur = 0
            if t.start_time and t.end_time:
                s = t.start_time.hour * 60 + t.start_time.minute
                e = t.end_time.hour * 60 + t.end_time.minute
                dur = max(0, e - s)

            # weeks string (master_class may store weeks/teaching_weeks)
            weeks_str = ""
            mc = getattr(t, "master_class", None)
            if mc:
                weeks_str = getattr(mc, "weeks", "") or ""
                if not weeks_str:
                    tw = getattr(mc, "teaching_weeks", None)
                    weeks_str = str(tw) if tw is not None else ""

            unit = t.unit_course.unit if t.unit_course else None
            campus_name = t.campus.campus_name if t.campus else ""

            # Be defensive: older DBs may not have 'notes' column yet
            try:
                notes_val = t.notes or ""
            except Exception:
                notes_val = ""

            # tutor may be missing / NULL
            tutor_name = ""
            tutor_email = ""
            try:
                if getattr(t, "tutor_user", None):
                    tutor_name = t.tutor_user.get_full_name() or ""
                    tutor_email = t.tutor_user.email or ""
            except Exception:
                pass

            rows.append({
                "session_id":   getattr(t, "timetable_id", t.pk),
                "activity_code": (unit.unit_code if unit else "")[:6].upper(),
                "unit_name":     unit.unit_name if unit else "",
                "campus":        campus_name,
                "day_of_week":   DAY_MAP.get(t.day_of_week, t.day_of_week),
                "start_time":    t.start_time.strftime("%H:%M") if t.start_time else "",
                "end_time":      t.end_time.strftime("%H:%M") if t.end_time else "",
                "duration":      dur,
                "location":      t.room or "",
                "weeks":         weeks_str,
                "notes":         notes_val,        # <- safe for old DBs
                "tutor":         tutor_name,
                "tutor_email":   tutor_email,
            })

    return JsonResponse(rows, safe=False)

class SendEmailWithAttachmentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        data = request.data
        to = (data.get("to") or "").strip()
        subject = (data.get("subject") or "Timetable").strip()
        body = data.get("body") or ""

        # Accept file from multipart
        f = request.FILES.get("attachment")
        if not to or not f:
            return Response({"detail": "Missing recipient or attachment"}, status=400)

        msg = EmailMessage(subject=subject, body=body, to=[to])
        msg.attach(getattr(f, "name", "timetable"),
                   f.read(),
                   getattr(f, "content_type", "application/octet-stream"))
        msg.send(fail_silently=False)
        return Response({"ok": True}, status=200)