# backend/semesters/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from django.db.utils import OperationalError
from users.permissions import IsAdminRole
from .serializers import SemesterSerializer, CreateSemesterSerializer, SelectViewSerializer
from .models import Semester
from .services import create_semester_db, set_view_semester, set_current_semester, list_existing_semesters, ensure_migrated

class SemesterListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_existing_semesters()
        return Response(SemesterSerializer(qs, many=True).data)


class SemesterCreateView(APIView):
    """
    Creates the physical semester database (via create_semester_db) and
    IMMEDIATELY migrates it so schema matches the codebase.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        s = CreateSemesterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            sem = create_semester_db(actor=request.user, **s.validated_data)

            # Ensure the new DB has all tables/columns (e.g. eoi_app.tutor_email)
            ensure_migrated(sem.alias)

        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        except OperationalError as e:
            # e.g., cannot connect/create or migration failure
            return Response({"detail": str(e)}, status=400)

        return Response(SemesterSerializer(sem).data, status=201)


class SemesterSelectView(APIView):
    """
    Set *viewing* semester (read-only). Pass {"alias": null} to revert to current.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = SelectViewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        alias = s.validated_data.get("alias") or None
        if alias and not Semester.objects.filter(alias=alias).exists():
            return Response({"detail": "Unknown alias"}, status=404)
        set_view_semester(request, alias)
        return Response({"ok": True})


class SemesterSetCurrentView(APIView):
    """
    Marks an existing semester as *current* and ensures its schema is up-to-date.
    This avoids 1054 Unknown column errors when the UI switches to the new current DB.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, alias):
        if not Semester.objects.filter(alias=alias).exists():
            return Response({"detail": "Unknown alias"}, status=404)

        try:
            set_current_semester(alias)
            # Make sure current semester DB is fully migrated before anyone uses it
            ensure_migrated(alias)

        except OperationalError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"ok": True})