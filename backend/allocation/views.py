from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Allocation
from eoi.models import EoiApp
from .serializers import AllocationSerializer, ManualAssignSerializer
from timetable.models import TimeTable
from django.contrib.auth import get_user_model

User = get_user_model()


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