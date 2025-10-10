# allocation/views.py
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q, Min
from rest_framework import generics, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import re

from .models import Allocation
from eoi.models import EoiApp
from .serializers import AllocationSerializer, ManualAssignSerializer, AssignRequestSerializer
from timetable.models import TimeTable
from timetable.serializers import TimeTableSessionSerializer
from semesters.threadlocal import force_write_alias
from semesters.router import get_current_semester_alias
from users.models import User, Campus
from units.models import Unit, UnitCourse
from users.permissions import IsAdminOrCoordinator

User = get_user_model()

def _get_alias(request):
    return request.query_params.get("alias") or get_current_semester_alias()


class AssignSer(serializers.Serializer):
    session_id = serializers.IntegerField()
    tutor_id = serializers.IntegerField()
    preference = serializers.IntegerField(required=False, default=0)


class AllocationListView(generics.ListAPIView):
    """
    List all allocations in a semester (optionally filter by ?year=&term=).
    """
    serializer_class = AllocationSerializer
    permission_classes = [IsAdminOrCoordinator]

    def get_queryset(self):
        alias = _get_alias(self.request)

        qs = (Allocation.objects.using(alias)
              .select_related(
                  "session",
                  "session__unit_course",
                  "session__unit_course__unit",
                  "tutor",
              ))

        year = self.request.query_params.get("year")
        term = self.request.query_params.get("term")

        if year:
            qs = qs.filter(session__unit_course__year=year)
        if term:
            qs = qs.filter(session__unit_course__term=term)

        return qs

class UnitsForAllocationView(APIView):
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request):
        alias = request.query_params.get("alias") or get_current_semester_alias()

        # Explicitly read from the semester DB, not the default DB
        qs = (TimeTable.objects.using(alias)
              .select_related("unit_course", "unit_course__unit", "unit_course__campus", "tutor_user")
              .all())

        buckets = {}
        for tt in qs:
            unit = tt.unit_course.unit if tt.unit_course else None
            if not unit:
                # skip rows that somehow lack a unit_course->unit
                continue

            campus_name = ""
            if tt.unit_course and tt.unit_course.campus:
                campus_name = tt.unit_course.campus.campus_name

            key = (unit.unit_code, unit.unit_name, campus_name)
            if key not in buckets:
                buckets[key] = {
                    "unit_code": unit.unit_code,
                    "unit_name": unit.unit_name,
                    "campus": campus_name,
                    "session_count": 0,
                    "tutors": {},
                }

            rec = buckets[key]
            rec["session_count"] += 1

            if tt.tutor_user_id:
                full = f"{tt.tutor_user.first_name} {tt.tutor_user.last_name}".strip() or (tt.tutor_user.email or "")
                email = tt.tutor_user.email or ""
                tkey = email or full
                if tkey:
                    rec["tutors"][tkey] = {"name": full, "email": email}

        data = []
        for rec in buckets.values():
            data.append({
                "unit_code": rec["unit_code"],
                "unit_name": rec["unit_name"],
                "campus": rec["campus"],
                "session_count": rec["session_count"],
                "tutors": list(rec["tutors"].values()),
            })

        data.sort(key=lambda x: (x["unit_code"], x["campus"]))
        return Response(data)
    
class ManualAssignView(APIView):
    """
    Manually assign a tutor to a class slot.
    """
    permission_classes = [IsAdminOrCoordinator]

    def post(self, request):
        alias = _get_alias(request)                                # <— NEW
        serializer = ManualAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with force_write_alias(alias):
            session = get_object_or_404(TimeTable.objects.using(alias), pk=serializer.validated_data["session_id"])
            tutor = get_object_or_404(User.objects.using(alias), pk=serializer.validated_data["tutor_id"])
            clashes = (TimeTable.objects.using(alias)
                    .filter(tutor_user=tutor, day_of_week=session.day_of_week,
                            start_time__lt=session.end_time, end_time__gt=session.start_time)
                    .exclude(pk=session.pk))
            if clashes.exists():
                return Response({"detail": "Clash detected"}, status=400)

            allocation = Allocation.objects.using(alias).create(   # <-- using(alias)
                session=session,
                tutor=tutor,
                preference=serializer.validated_data.get("preference", 0),
                status="completed",
                created_by=request.user,
            )
            return Response(AllocationSerializer(allocation).data, status=201)

class AutoAllocateView(APIView):
    """
    Allocate tutors automatically based on EOI preference values
    within the selected semester DB (alias).
    """
    permission_classes = [IsAdminOrCoordinator]

    def post(self, request):
        alias = request.GET.get("alias") or request.data.get("alias") or _get_alias(request)
        if not alias or alias == "default":
            return Response({"detail": "No semester alias provided."}, status=400)

        term = request.data.get("term")
        year = request.data.get("year")

        # All reads/writes happen on the semester DB
        with force_write_alias(alias):
            qs = TimeTable.objects.using(alias).select_related("unit_course", "unit_course__unit")

            if year:
                qs = qs.filter(unit_course__year=year)
            if term:
                qs = qs.filter(unit_course__term=term)

            created = []

            for s in qs:
                # Skip rows without a unit (shouldn't happen, but defensive)
                if not s.unit_course or not s.unit_course.unit:
                    continue

                # Idempotent: skip if an allocation already exists for this session
                if Allocation.objects.using(alias).filter(session=s).exists():
                    continue

                # Consider EOIs for this unit ordered by best preference
                eois = (EoiApp.objects.using(alias)
                        .filter(unit=s.unit_course.unit, preference__gte=1)
                        .order_by("preference", "id"))

                for e in eois:
                    # Extra safety, though preference__gte=1 already filters this
                    if not e.preference or e.preference < 1:
                        continue

                    # Clash: same tutor overlapping time on the same day
                    clash_exists = (TimeTable.objects.using(alias)
                                    .filter(
                                        tutor_user=e.applicant_user,
                                        day_of_week=s.day_of_week,
                                        start_time__lt=s.end_time,
                                        end_time__gt=s.start_time,
                                    )
                                    .exclude(pk=s.pk)
                                    .exists())
                    if clash_exists:
                        continue

                    alloc = Allocation.objects.using(alias).create(
                        session=s,
                        tutor=e.applicant_user,
                        preference=e.preference,
                        status="completed",
                        created_by=request.user,
                    )
                    created.append(alloc)
                    break  # move to next session after first non-clashing tutor

        return Response(
            {"created": len(created), "allocations": AllocationSerializer(created, many=True).data},
            status=200,
        )

class ApproveAllocationsView(APIView):
    """
    Mark all allocations in a semester as approved and publish.
    """
    permission_classes = [IsAdminOrCoordinator]

    def post(self, request):
        alias = request.GET.get("alias") or request.data.get("alias") or _get_alias(request)
        if not alias or alias == "default":
            return Response({"detail": "No semester alias provided."}, status=400)

        term = request.data.get("term")
        year = request.data.get("year")

        with force_write_alias(alias):
            qs = Allocation.objects.using(alias).all()
            if term:
                qs = qs.filter(session__unit_course__term=term)
            if year:
                qs = qs.filter(session__unit_course__year=year)
            qs.update(approved=True)

        return Response({"detail": "Allocations approved and published."})

class TutorTimetableView(APIView):
    """
    Tutors can view their published timetable.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, tutor_id=None):
        alias = _get_alias(request) 
        with force_write_alias(alias):
            if tutor_id is None:
                tutor = User.objects.using(alias).filter(email__iexact=request.user.email).first()
                if not tutor:
                    return Response([], status=200)
            else:
                tutor = get_object_or_404(User.objects.using(alias), pk=tutor_id)

            qs = (Allocation.objects.using(alias)   # <-- using(alias)
                .filter(tutor=tutor, approved=True)
                .select_related("session", "session__unit_course", "session__unit_course__unit"))
            return Response(AllocationSerializer(qs, many=True).data)
        
class SessionsByUnitCode(APIView):
    """Alias-aware sessions for one unit code; optional campus filter."""
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request):
        alias = _get_alias(request)
        code = request.query_params.get("unit_code")
        campus = request.query_params.get("campus")
        if not code:
            return Response([], status=200)

        # ✅ read from the semester DB explicitly
        qs = (TimeTable.objects.using(alias)
              .select_related("unit_course", "unit_course__unit", "unit_course__campus",
                              "tutor_user", "master_class")
              .filter(unit_course__unit__unit_code__iexact=code))
        if campus:
            qs = qs.filter(unit_course__campus__campus_name__iexact=campus)

        rows = []
        for tt in qs.order_by("day_of_week", "start_time", "timetable_id"):
            u = tt.unit_course.unit if tt.unit_course else None
            # safe access for optional columns
            activity = getattr(getattr(tt, "master_class", None), "activity_code", None) or ""
            weeks    = getattr(getattr(tt, "master_class", None), "weeks", "") or ""
            try:
                notes = tt.notes or ""
            except Exception:
                notes = ""

            rows.append({
                "session_id": tt.timetable_id,
                "unit_name": u.unit_name if u else "",
                "activity_code": activity,
                "campus": tt.unit_course.campus.campus_name if (tt.unit_course and tt.unit_course.campus) else "",
                "day_of_week": tt.day_of_week,
                "start_time": str(tt.start_time) if tt.start_time else None,
                "end_time": str(tt.end_time) if tt.end_time else None,
                "duration": getattr(tt, "duration_minutes", None),
                "location": tt.room or "",
                "weeks": weeks,
                "tutor": (f"{tt.tutor_user.first_name} {tt.tutor_user.last_name}".strip() if tt.tutor_user else ""),
                "tutor_email": (tt.tutor_user.email if tt.tutor_user else ""),
                "tutor_user_id": tt.tutor_user_id,
                "notes": notes,
            })
        return Response(rows, status=200)

class UnitSessionsView(APIView):
    """Return all sessions for one unit code (optionally filtered by campus)."""
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request, unit_code):
        alias = _get_alias(request)
        campus = request.query_params.get("campus")

        qs = (TimeTable.objects.using(alias)                       # ✅ here
              .select_related("unit_course", "unit_course__unit", "unit_course__campus", "tutor_user")
              .filter(unit_course__unit__unit_code__iexact=unit_code))
        if campus:
            qs = qs.filter(unit_course__campus__campus_name__iexact=campus)

        rows = []
        for tt in qs.order_by("day_of_week", "start_time", "pk"):
            u = tt.unit_course.unit if tt.unit_course else None
            try:
                notes = tt.notes or ""
            except Exception:
                notes = ""
            rows.append({
                "id": tt.pk,
                "unit_code": u.unit_code if u else "",
                "unit_name": u.unit_name if u else "",
                "campus": tt.unit_course.campus.campus_name if (tt.unit_course and tt.unit_course.campus) else "",
                "day": tt.day_of_week,
                "start_time": str(tt.start_time) if tt.start_time else None,
                "end_time": str(tt.end_time) if tt.end_time else None,
                "location": tt.room or "",
                "tutor": (f"{tt.tutor_user.first_name} {tt.tutor_user.last_name}".strip() if tt.tutor_user else ""),
                "tutor_email": (tt.tutor_user.email if tt.tutor_user else ""),
                "notes": notes,
            })
        return Response(rows)
    
class SuggestTutorsView(APIView):
    """
    Suggest tutors for a unit (and campus) ordered by EOI preference asc.
    Query: unit_code=KIT101&campus=SB&q=pha
    """
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request):
        alias = _get_alias(request)
        unit_code = request.query_params.get("unit_code", "")
        campus = request.query_params.get("campus", "")
        q = request.query_params.get("q", "").strip()

        if not unit_code:
            return Response([], status=200)

        with force_write_alias(alias):
            eoi = (EoiApp.objects.using(alias)  # <-- using(alias)
                .filter(unit__unit_code__iexact=unit_code))
            if campus:
                eoi = eoi.filter(campus__campus_name__iexact=campus)

            pref_map = (eoi.values("applicant_user_id").annotate(best_pref=Min("preference")))
            pref_by_user = {r["applicant_user_id"]: (r["best_pref"] or 9999) for r in pref_map}

            users = User.objects.using(alias).all()  # <-- using(alias)
            if q:
                users = users.filter(
                    Q(first_name__icontains=q) |
                    Q(last_name__icontains=q) |
                    Q(email__icontains=q)
                )
            only_eoi_ids = set(pref_by_user.keys())
            if only_eoi_ids:
                users = users.filter(id__in=only_eoi_ids)

            results = []
            for u in users:
                pref = pref_by_user.get(u.id, 9999)
                results.append({
                    "id": u.id,
                    "name": f"{u.first_name} {u.last_name}".strip() or u.email,
                    "email": u.email,
                    "preference": pref if pref < 9999 else None,
                })

            results.sort(key=lambda r: (r["preference"] is None, r["preference"] or 9999, r["name"].lower()))
            return Response(results)


class AssignTutorView(APIView):
    permission_classes = [IsAdminOrCoordinator]

    def post(self, request):
        alias = _get_alias(request)
        session_id = request.data.get("session_id")
        tutor_id = request.data.get("tutor_id")
        tutor_email = request.data.get("tutor_email")
        notes = request.data.get("notes", "")

        if not session_id:
            return Response({"detail": "session_id is required"}, status=400)

        with force_write_alias(alias):
            try:
                tt = TimeTable.objects.using(alias).get(pk=session_id)     # <-- using(alias)
            except TimeTable.DoesNotExist:
                return Response({"detail": "Session not found"}, status=404)

            tutor = None
            if tutor_id:
                try:
                    tutor = User.objects.using(alias).get(pk=tutor_id)     # <-- using(alias)
                except User.DoesNotExist:
                    return Response({"detail": f"Tutor id {tutor_id} not found"}, status=404)
            elif tutor_email:
                tutor = User.objects.using(alias).filter(email__iexact=tutor_email).first()  # <-- using(alias)
                if not tutor:
                    return Response({"detail": f"Tutor email {tutor_email} not found"}, status=404)

            if tutor:
                ok, msg = tt.can_assign_tutor(tutor)
                if not ok:
                    return Response({"detail": msg}, status=400)
                tt.tutor_user = tutor
            else:
                tt.tutor_user = None  # unassign

            tt.notes = notes
            tt.save(using=alias)

            return Response({
                "ok": True,
                "session_id": tt.pk,
                "tutor_user_id": tt.tutor_user_id,
                "tutor": tt.tutor_user.get_full_name() if tt.tutor_user else "",
                "tutor_email": tt.tutor_user.email if tt.tutor_user else "",
                "notes": tt.notes,
            })


class RunAllocationView(APIView):
    """
    Runs a simple automatic allocation for the current semester DB.
    """
    permission_classes = [IsAdminOrCoordinator]

    def post(self, request):
        alias = request.GET.get("alias") or request.data.get("alias") or _get_alias(request)
        if not alias or alias == "default":
            return Response({"detail": "No semester alias provided."}, status=400)

        # Try to infer year/term from alias like 'sem_2023_s4'
        year = term = None
        m_year = re.search(r"(\d{4})", alias or "")
        if m_year:
            year = int(m_year.group(1))
        m_term = re.search(r"(?:[sStT])(\d+)", alias or "")
        if m_term:
            term = int(m_term.group(1))

        created = []

        with force_write_alias(alias):
            qs = TimeTable.objects.using(alias).select_related("unit_course", "unit_course__unit")
            if year is not None and term is not None:
                qs = qs.filter(unit_course__year=year, unit_course__term=term)

            for s in qs:
                # Skip if already allocated on this semester DB
                if Allocation.objects.using(alias).filter(session=s).exists():
                    continue

                # EOIs for the unit, ordered by best preference
                eois = (EoiApp.objects.using(alias)
                        .filter(unit=s.unit_course.unit)
                        .order_by("preference", "id"))

                for e in eois:
                    # Clash with existing allocations for this tutor?
                    clash = (Allocation.objects.using(alias)
                             .filter(
                                 tutor=e.applicant_user,
                                 session__day_of_week=s.day_of_week,
                                 session__start_time__lt=s.end_time,
                                 session__end_time__gt=s.start_time,
                             )
                             .exists())
                    if clash:
                        continue

                    alloc, _ = Allocation.objects.using(alias).get_or_create(
                        session=s,
                        tutor=e.applicant_user,
                        defaults={
                            "preference": e.preference,
                            "status": "completed",
                            "approved": False,
                            "created_by": request.user,
                        },
                    )
                    created.append(alloc)
                    break  # next session after first valid tutor

        return Response(
            {"created": len(created), "allocations": AllocationSerializer(created, many=True).data},
            status=status.HTTP_200_OK,
        )
