<<<<<<< Updated upstream
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
from django.db import connections
from django.db.utils import OperationalError
import pandas as pd
from .models import EoiApp
from units.models import Unit
from django.contrib.auth import get_user_model
from .serializers import EoiAppSerializer
from semesters.router import get_current_semester_alias

User = get_user_model()

class EOIUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(file_obj)
        except Exception as e:
            return Response({"detail": f"Error reading Excel: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        alias = get_current_semester_alias() or "default"

        created = []
        for _, row in df.iterrows():
            unit_code = str(row.get("Unit Code") or "").strip()
            unit_name = str(row.get("Unit Name") or "").strip()
            email = str(row.get("Tutor Email") or "").strip()

            if not unit_code or not email:
                continue

            unit, _ = Unit.objects.using(alias).get_or_create(
                unit_code=unit_code, defaults={"unit_name": unit_name}
            )
            tutor, _ = User.objects.using(alias).get_or_create(
                email=email, defaults={"username": email.split("@")[0]}
            )

            eoi, _ = EoiApp.objects.using(alias).update_or_create(
                applicant_user=tutor,
                unit=unit,
                defaults={
                    "status": "Submitted",
                    "preference": int(row.get("Preference", 0)),
                    "qualifications": row.get("Qualifications", ""),
                    "availability": row.get("Availability", ""),
                },
            )
            created.append(eoi.scd_id)

        return Response({"created": len(created)}, status=status.HTTP_201_CREATED)

class ApplicantsByUnit(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = (request.query_params.get("unit_code") or "").strip().upper()
        if not code:
            return Response({"error": "unit_code is required"}, status=400)

        # allow overriding alias via ?alias=… but default to current
        alias = (request.query_params.get("alias") or
                 get_current_semester_alias() or
                 "default")

        qs = (
            EoiApp.objects.using(alias)
            .select_related("applicant_user", "unit", "campus")
            .filter(is_current=True, unit__unit_code=code)
            .order_by("preference", "applicant_user__username")
        )
        data = EoiAppSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)

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

        # Resolve unit_id if only unit_code provided
        unit_id = ser.validated_data.get("unit_id")
        if not unit_id:
            try:
                unit_id = Unit.objects.using(alias).only("id").get(
                    unit_code__iexact=ser.validated_data["unit_code"]
                ).pk
            except Unit.DoesNotExist:
                return Response({"detail": "Unknown unit."}, status=status.HTTP_400_BAD_REQUEST)

        updated = 0
        for row in ser.validated_data["prefs"]:
            email = (row.get("email") or "").strip().lower()
            try:
                pref = int(row.get("preference") or 0)
            except (TypeError, ValueError):
                pref = 0
            if not email or pref <= 0:
                continue

            # Update by tutor_email OR applicant_user.email (whichever exists)
            qs = EoiApp.objects.using(alias).filter(unit_id=unit_id, is_current=True)

            if _column_exists(alias, "eoi_app", "tutor_email"):
                qs = qs.filter(
                    Q(tutor_email__iexact=email) | Q(applicant_user__email__iexact=email)
                )
            else:
                # legacy DB without the new column
                qs = qs.filter(applicant_user__email__iexact=email)

            updated += qs.update(preference=pref)

=======
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
import pandas as pd
from .models import EoiApp
from units.models import Unit
from django.contrib.auth import get_user_model
from .serializers import EoiAppSerializer
from semesters.router import get_current_semester_alias

User = get_user_model()

class EOIUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(file_obj)
        except Exception as e:
            return Response({"detail": f"Error reading Excel: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        alias = get_current_semester_alias() or "default"

        created = []
        for _, row in df.iterrows():
            unit_code = str(row.get("Unit Code") or "").strip()
            unit_name = str(row.get("Unit Name") or "").strip()
            email = str(row.get("Tutor Email") or "").strip()

            if not unit_code or not email:
                continue

            unit, _ = Unit.objects.using(alias).get_or_create(
                unit_code=unit_code, defaults={"unit_name": unit_name}
            )
            tutor, _ = User.objects.using(alias).get_or_create(
                email=email, defaults={"username": email.split("@")[0]}
            )

            eoi, _ = EoiApp.objects.using(alias).update_or_create(
                applicant_user=tutor,
                unit=unit,
                defaults={
                    "status": "Submitted",
                    "preference": int(row.get("Preference", 0)),
                    "qualifications": row.get("Qualifications", ""),
                    "availability": row.get("Availability", ""),
                },
            )
            created.append(eoi.scd_id)

        return Response({"created": len(created)}, status=status.HTTP_201_CREATED)

class ApplicantsByUnit(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        unit_code = request.query_params.get("unit_code")
        unit_id   = request.query_params.get("unit_id")

        alias = get_current_semester_alias() or "default"

        qs = (
            EoiApp.objects.using(alias)
            .select_related("applicant_user", "unit", "campus")
            .filter(is_current=True)
        )

        if unit_id:
            qs = qs.filter(unit_id=unit_id)
        elif unit_code:
            qs = qs.filter(unit__unit_code__iexact=unit_code)
        else:
            return Response({"detail": "unit_code or unit_id is required"}, status=400)

        qs = qs.order_by("tutor_name", "applicant_user__first_name", "applicant_user__last_name")

        data = EoiAppSerializer(qs, many=True).data
        return Response(data, status=200)
    
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

        # Resolve unit_id if only unit_code provided
        unit_id = ser.validated_data.get("unit_id")
        if not unit_id:
            try:
                unit_id = Unit.objects.using(alias).only("id").get(
                    unit_code__iexact=ser.validated_data["unit_code"]
                ).pk
            except Unit.DoesNotExist:
                return Response({"detail": "Unknown unit."}, status=status.HTTP_400_BAD_REQUEST)

        updated = 0
        for row in ser.validated_data["prefs"]:
            email = (row.get("email") or "").strip().lower()
            try:
                pref = int(row.get("preference") or 0)
            except (TypeError, ValueError):
                pref = 0
            if not email or pref <= 0:
                continue

            # Update by tutor_email OR applicant_user.email (whichever exists)
            qs = (
                EoiApp.objects.using(alias)
                .filter(unit_id=unit_id, is_current=True)
                .filter(Q(tutor_email__iexact=email) | Q(applicant_user__email__iexact=email))
            )
            updated += qs.update(preference=pref)

>>>>>>> Stashed changes
        return Response({"updated": updated}, status=status.HTTP_200_OK)