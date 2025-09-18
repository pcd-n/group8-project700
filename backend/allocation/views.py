#allocation/views.py
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

User = get_user_model()

def _get_alias(request):
    return request.query_params.get("alias") or get_current_semester_alias()

class AssignSer(serializers.Serializer):
    session_id = serializers.IntegerField()
    tutor_id = serializers.IntegerField()
    preference = serializers.IntegerField(required=False, default=0)

class AssignTutor(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = AssignSer(data=request.data)
        ser.is_valid(raise_exception=True)
        tt = TimeTable.objects.get(pk=ser.validated_data["session_id"])
        tutor = User.objects.get(pk=ser.validated_data["tutor_id"])
        alloc, _ = Allocation.objects.get_or_create(
            session=tt, tutor=tutor, defaults={"created_by": request.user}
        )
        # update optional fields
        alloc.preference = ser.validated_data.get("preference", alloc.preference)
        alloc.status = "completed"
        alloc.approved = False
        alloc.save()
        return Response({"ok": True, "allocation_id": alloc.id}, status=status.HTTP_200_OK)
    
class AllocationListView(generics.ListAPIView):
    """
    List all allocations in a semester (filter by year/term).
    """
    serializer_class = AllocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Allocation.objects.all()
        year = self.request.query_params.get("year")
        term = self.request.query_params.get("term")
        if year and term:
            qs = qs.filter(
                session__unit_course__year=year,
                session__unit_course__term=term
            )
        return qs

class UnitsForAllocationView(APIView):
    """Return [{code, name, campus_name, sessions}] for the given alias."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        alias = _get_alias(request)
        with force_write_alias(alias):
            qs = (TimeTable.objects
                  .select_related("unit_course", "unit_course__unit", "unit_course__campus")
                  .all())
            seen = {}
            for tt in qs:
                unit = tt.unit_course.unit
                campus = tt.unit_course.campus.campus_name if tt.unit_course.campus else ""
                key = (unit.unit_code, unit.unit_name, campus)
                seen.setdefault(key, 0)
                seen[key] += 1
            data = [
                {"unit_code": u, "unit_name": n, "campus": c, "session_count": cnt}
                for (u, n, c), cnt in seen.items()
            ]
            data.sort(key=lambda x: (x["unit_code"], x["campus"]))
            return Response(data)

class ManualAssignView(APIView):
    """
    Manually assign a tutor to a class slot.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ManualAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = get_object_or_404(TimeTable, pk=serializer.validated_data["session_id"])
        tutor = get_object_or_404(User, pk=serializer.validated_data["tutor_id"])

        # clash check
        clashes = Allocation.objects.filter(
            tutor=tutor,
            session__day_of_week=session.day_of_week,
            session__start_time__lt=session.end_time,
            session__end_time__gt=session.start_time,
        )
        if clashes.exists():
            return Response({"detail": "Clash detected"}, status=400)

        allocation = Allocation.objects.create(
            session=session,
            tutor=tutor,
            preference=serializer.validated_data.get("preference", 0),
            status="completed",
            created_by=request.user,
        )
        return Response(AllocationSerializer(allocation).data, status=201)


class AutoAllocateView(APIView):
    """
    Allocate tutors automatically based on EOI preference values.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        term = request.data.get("term")
        year = request.data.get("year")

        qs = TimeTable.objects.all()
        if year:
            qs = qs.filter(unit_course__year=year)
        if term:
            qs = qs.filter(unit_course__term=term)

        sessions = qs
        created = []

        for s in sessions:
            # skip if already allocated
            if Allocation.objects.filter(session=s).exists():
                continue

            # EOIs for this unit ordered by preference
            eois = EoiApp.objects.filter(unit=s.unit_course.unit).order_by("preference")
            allocated = False
            for e in eois:
                clashes = Allocation.objects.filter(
                    tutor=e.applicant_user,
                    session__day_of_week=s.day_of_week,
                    session__start_time__lt=s.end_time,
                    session__end_time__gt=s.start_time,
                )
                if not clashes.exists():
                    alloc = Allocation.objects.create(
                        session=s,
                        tutor=e.applicant_user,
                        preference=e.preference,
                        status="completed",
                        created_by=request.user,
                    )
                    created.append(alloc)
                    allocated = True
                    break

        return Response(AllocationSerializer(created, many=True).data)


class ApproveAllocationsView(APIView):
    """
    Mark all allocations in a semester as approved and publish.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        term = request.data.get("term")
        year = request.data.get("year")

        qs = Allocation.objects.filter(
            session__unit_course__term=term,
            session__unit_course__year=year
        )
        qs.update(approved=True)

        return Response({"detail": "Allocations approved and published."})


class TutorTimetableView(APIView):
    """
    Tutors can view their published timetable.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, tutor_id=None):
        tutor = request.user if tutor_id is None else get_object_or_404(User, pk=tutor_id)
        qs = Allocation.objects.filter(tutor=tutor, approved=True)
        return Response(AllocationSerializer(qs, many=True).data)

class SessionsByUnitCode(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("unit_code")
        if not code:
            return Response([], status=200)

        qs = TimeTable.objects.filter(unit__unit_code__iexact=code).select_related("unit").prefetch_related("allocations__tutor")
        data = TimeTableSessionSerializer(qs, many=True).data
        return Response(data, status=200)

class UnitSessionsView(APIView):
    """Return all sessions for one unit code (optionally filtered by campus)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_code):
        alias = _get_alias(request)
        campus = request.query_params.get("campus")  # SB / IR / ONLINE optional
        with force_write_alias(alias):
            qs = (TimeTable.objects
                  .select_related("unit_course", "unit_course__unit", "unit_course__campus", "tutor_user")
                  .filter(unit_course__unit__unit_code__iexact=unit_code))
            if campus:
                qs = qs.filter(unit_course__campus__campus_name__iexact=campus)
            rows = []
            for tt in qs.order_by("day_of_week", "start_time", "id"):
                u = tt.unit_course.unit
                rows.append({
                    "id": tt.id,
                    "unit_code": u.unit_code,
                    "unit_name": u.unit_name,
                    "campus": tt.unit_course.campus.campus_name if tt.unit_course.campus else "",
                    "day": tt.day_of_week,
                    "start_time": str(tt.start_time) if tt.start_time else None,
                    "end_time": str(tt.end_time) if tt.end_time else None,
                    "location": tt.room,
                    "tutor": (f"{tt.tutor_user.first_name} {tt.tutor_user.last_name}".strip()
                              if tt.tutor_user else ""),
                    "tutor_email": (tt.tutor_user.email if tt.tutor_user else ""),
                    "notes": tt.notes or "",
                })
            return Response(rows)

class SuggestTutorsView(APIView):
    """
    Suggest tutors for a unit (and campus) ordered by EOI preference asc (1 best), 
    then by name if no preference.
    Query params: unit_code=KIT101&campus=SB&q=pha
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        alias = _get_alias(request)
        unit_code = request.query_params.get("unit_code", "")
        campus = request.query_params.get("campus", "")
        q = request.query_params.get("q", "").strip()

        if not unit_code:
            return Response([], status=200)

        with force_write_alias(alias):
            eoi = (EoiApp.objects
                   .filter(unit__unit_code__iexact=unit_code))
            if campus:
                eoi = eoi.filter(campus__campus_name__iexact=campus)

            # build a map: user_id -> best preference (min)
            pref_map = (eoi.values("applicant_user_id")
                          .annotate(best_pref=Min("preference")))
            pref_by_user = {r["applicant_user_id"]: (r["best_pref"] or 9999)
                            for r in pref_map}

            users = User.objects.using(alias).all()
            if q:
                users = users.filter(
                    Q(first_name__icontains=q) |
                    Q(last_name__icontains=q) |
                    Q(email__icontains=q)
                )

            # only include users who have EOI for this unit if any exist; otherwise show everyone
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

            # order: have preference (ascending), then name
            results.sort(key=lambda r: (r["preference"] is None, r["preference"] or 9999, r["name"].lower()))
            return Response(results)

class AssignTutorView(APIView):
    """Assign a tutor (by user_id or email) and set notes for a timetable session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        alias = _get_alias(request)
        s = AssignRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        with force_write_alias(alias):
            tt = TimeTable.objects.select_related("unit_course").filter(id=data["session_id"]).first()
            if not tt:
                return Response({"detail": "Session not found."}, status=404)

            tutor = None
            if data.get("tutor_user_id"):
                tutor = User.objects.using(alias).filter(id=data["tutor_user_id"]).first()
            elif data.get("tutor_email"):
                tutor = User.objects.using(alias).filter(email__iexact=data["tutor_email"]).first()
            if not tutor:
                return Response({"detail": "Tutor not found."}, status=400)

            # optional simple clash check: same day overlapping time
            if tt.start_time and tt.end_time:
                clash = TimeTable.objects.filter(
                    tutor_user=tutor,
                    day_of_week=tt.day_of_week,
                    start_time__lt=tt.end_time,
                    end_time__gt=tt.start_time,
                ).exclude(id=tt.id).exists()
                if clash:
                    return Response({"detail": "Tutor has a time clash for this session."}, status=409)

            tt.tutor_user = tutor
            if data.get("notes") is not None:
                tt.notes = data["notes"]
            tt.save(update_fields=["tutor_user", "notes"])
            return Response({"ok": True})
           
class RunAllocationView(APIView):
    """
    Runs a simple automatic allocation for the current semester DB.
    Optional ?alias=sem_2023_s4 switches the write alias during the run.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        alias = request.GET.get("alias") or request.data.get("alias")
        ctx = force_write_alias(alias) if alias else None
        if ctx:
            ctx.__enter__()

        try:
            qs = TimeTable.objects.all()

            # Try to filter by year/term if we can extract them from alias like 'sem_2023_s4'
            year = term = None
            if alias:
                m_year = re.search(r"(\d{4})", alias)
                if m_year:
                    year = int(m_year.group(1))
                m_term = re.search(r"(?:[sStT])(\d+)", alias)
                if m_term:
                    term = int(m_term.group(1))
            if year is not None and term is not None:
                qs = qs.filter(unit_course__year=year, unit_course__term=term)

            created = []
            # Naive allocator: for each timetable session without an allocation,
            # try tutors (EOIs) in ascending preference; skip on clash.
            for s in qs.select_related("unit_course", "unit_course__unit"):
                if Allocation.objects.filter(session=s).exists():
                    continue

                eois = (
                    EoiApp.objects
                    .filter(unit=s.unit_course.unit)
                    .order_by("preference", "id")
                )

                for e in eois:
                    # clash check: same day overlap
                    clash = Allocation.objects.filter(
                        tutor=e.applicant_user,
                        session__day_of_week=s.day_of_week,
                        session__start_time__lt=s.end_time,
                        session__end_time__gt=s.start_time,
                    ).exists()
                    if clash:
                        continue

                    alloc, _ = Allocation.objects.get_or_create(
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
                    break  # stop scanning EOIs for this session once allocated

            return Response(
                {
                    "created": len(created),
                    "allocations": AllocationSerializer(created, many=True).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            if ctx:
                ctx.__exit__(None, None, None)
