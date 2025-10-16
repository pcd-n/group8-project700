# backend/semesters/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from django.db.utils import OperationalError
from users.permissions import IsAdminRole
from .serializers import SemesterSerializer, CreateSemesterSerializer, SelectViewSerializer
from .models import Semester
from django.db import connection, connections, transaction
from django.conf import settings
from .services import (
    create_semester_db, set_view_semester, set_current_semester,
    list_existing_semesters, ensure_migrated, get_active_semester_alias,
    db_name_for_alias, schema_exists_for_alias,
)

class SemesterListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = list_existing_semesters()
        return Response(SemesterSerializer(qs, many=True).data)


class SemesterCreateView(APIView):
    """
    Creates the physical semester database (via create_semester_db) and
    IMMEDIATELY migrates it so schema matches the codebase.
    """
    permission_classes = [IsAdminRole]

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
    permission_classes = [IsAdminRole]

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
    permission_classes = [IsAdminRole]
    def post(self, request, alias):
        if not Semester.objects.filter(alias=alias).exists():
            return Response({"detail": "Unknown alias"}, status=404)
        # migrate BEFORE exposing as current
        ensure_migrated(alias)
        set_current_semester(alias)
        set_view_semester(request, None)
        return Response({"ok": True})

class SemesterCurrentView(APIView):
    """
    Return the active alias the frontend should use.
    Priority: session view_alias -> current semester.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        alias = get_active_semester_alias(request)  # resolves view_semester or current
        if not alias:
            return Response({"alias": None}, status=200)
        # make sure alias exists and schema is ready (idempotent)
        ensure_migrated(alias)
        db_name = connections[alias].settings_dict.get("NAME", "")
        return Response({"alias": alias, "db": db_name}, status=200)

class SemesterDBListView(APIView):
    """Admin: list known semester aliases and their physical DB names."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        rows = []
        for s in Semester.objects.all().order_by("-is_current", "-year", "term"):
            dbname = s.db_name or db_name_for_alias(s.alias)
            rows.append({
                "alias": s.alias,
                "db": dbname,
                "year": s.year,
                "term": s.term,
                "is_current": s.is_current,
                "db_exists": schema_exists_for_alias(s.alias),
            })
        return Response(rows, status=200)

class SemesterDropDBView(APIView):
    """Admin: drop a semester database by alias (not allowed for current)."""
    permission_classes = [IsAdminRole]

    def delete(self, request, alias):
        # Safety checks
        try:
            sem = Semester.objects.get(alias=alias)
        except Semester.DoesNotExist:
            return Response({"detail": "Unknown alias"}, status=404)
        if sem.is_current:
            return Response({"detail": "Cannot drop the current semester DB."}, status=400)

        # Resolve physical DB name (prefer model; alias might not be registered)
        dbname = sem.db_name
        if not dbname:
            return Response({"detail": "No database name recorded for this semester."}, status=400)

        # Use the default connection to drop, even if alias is not registered
        with connections["default"].cursor() as c:
            c.execute(f"DROP DATABASE IF EXISTS `{dbname}`")

        # Remove the Semester record
        sem.delete()
        return Response(status=204)