#eoi/views.py
from semesters.router import get_current_semester_alias
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.db import connections, transaction
from django.db.utils import OperationalError
import pandas as pd
from .models import EoiApp
from units.models import Unit
from django.contrib.auth import get_user_model
from .serializers import EoiAppSerializer
from semesters.router import get_current_semester_alias
from semesters.services import ensure_migrated
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class EOIUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(f)
        except Exception as e:
            return Response({"detail": f"Error reading Excel: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        alias = get_current_semester_alias() or "default"
        ensure_migrated(alias)  # idempotent safety
        db = connections[alias].settings_dict.get("NAME")

        created = 0
        with transaction.atomic(using=alias):
            for _, row in df.iterrows():
                unit_code = str(row.get("Unit Code") or "").strip().upper()
                unit_name = str(row.get("Unit Name") or "").strip()
                email = str(row.get("Tutor Email") or "").strip().lower()
                if not unit_code or not email:
                    continue

                unit, _ = Unit.objects.using(alias).get_or_create(
                    unit_code=unit_code, defaults={"unit_name": unit_name or unit_code}
                )
                # EOI tutors should exist only in semester DB and usually is_active=False
                tutor, _ = User.objects.using(alias).get_or_create(
                    email=email,
                    defaults={"username": (email.split("@")[0] or "user")[:150], "is_active": False},
                )

                # defaults: preference/availability/qualifications if present
                defaults = {
                    "status": "Submitted",
                    "preference": int(row.get("Preference", 0) or 0),
                    "qualifications": row.get("Qualifications") or "",
                    "availability": row.get("Availability") or "",
                    "tutor_email": email,
                }
                EoiApp.objects.using(alias).update_or_create(
                    applicant_user=tutor, unit=unit, defaults=defaults
                )
                created += 1

        logger.info("EOIUpload: created/updated %d rows (alias=%s, db=%s)", created, alias, db)
        return Response({"created": created, "alias": alias, "db": db}, status=status.HTTP_201_CREATED)

class ApplicantsByUnit(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = (request.query_params.get("unit_code") or "").strip().upper()
        if not code:
            return Response({"detail": "unit_code is required"}, status=400)

        # allow overriding alias via ?alias=… but default to current
        alias = (request.query_params.get("alias")
                 or get_current_semester_alias()
                 or "default")

        ensure_migrated(alias)
        db = connections[alias].settings_dict.get("NAME")

        try:
            qs = (EoiApp.objects.using(alias)
                  .select_related("applicant_user", "unit", "campus")
                  .filter(is_current=True, unit__unit_code__iexact=code)
                  .order_by("preference", "applicant_user__username"))

            data = EoiAppSerializer(qs, many=True).data
            # Return a consistent shape; the page can handle list or {"results": list}.
            return Response({"results": data, "alias": alias, "db": db}, status=200)

        except Exception as e:
            logger.exception("ApplicantsByUnit failed (unit=%s alias=%s db=%s): %s", code, alias, db, e)
            return Response({"detail": str(e), "alias": alias, "db": db}, status=500)


def _column_exists(using: str, table: str, column: str) -> bool:
    with connections[using].cursor() as c:
        c.execute(f"SHOW COLUMNS FROM `{table}` LIKE %s", [column])
        return c.fetchone() is not None

class PreferenceItemSer(serializers.Serializer):
    email = serializers.EmailField()
    preference = serializers.IntegerField(min_value=1, max_value=10)

class SavePreferences(APIView):
    permission_classes = [IsAuthenticated]

    class BodySer(drf_serializers.Serializer):
        unit_id = drf_serializers.IntegerField(required=False)
        unit_code = drf_serializers.CharField(required=False, allow_blank=True)
        prefs = drf_serializers.ListField(child=drf_serializers.DictField(), allow_empty=False)

        def validate(self, data):
            if not data.get("unit_id") and not data.get("unit_code"):
                raise drf_serializers.ValidationError("unit_id or unit_code is required")
            return data

    def post(self, request):
        ser = self.BodySer(data=request.data)
        ser.is_valid(raise_exception=True)

        alias = get_current_semester_alias() or "default"
        ensure_migrated(alias)

        # Resolve unit_id if only unit_code provided
        unit_id = ser.validated_data.get("unit_id")
        if not unit_id:
            try:
                unit_id = Unit.objects.using(alias).only("id").get(
                    unit_code__iexact=ser.validated_data["unit_code"]
                ).pk
            except Unit.DoesNotExist:
                return Response({"detail": "Unknown unit."}, status=400)

        updated = 0
        for row in ser.validated_data["prefs"]:
            email = (row.get("email") or "").strip().lower()
            try:
                pref = int(row.get("preference") or 0)
            except (TypeError, ValueError):
                pref = 0
            if not email or pref <= 0:
                continue

            qs = EoiApp.objects.using(alias).filter(unit_id=unit_id, is_current=True)

            if _column_exists(alias, "eoi_app", "tutor_email"):
                qs = qs.filter(Q(tutor_email__iexact=email) | Q(applicant_user__email__iexact=email))
            else:
                qs = qs.filter(applicant_user__email__iexact=email)

            updated += qs.update(preference=pref)

        return Response({"updated": updated, "alias": alias}, status=200)