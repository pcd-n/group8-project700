from semesters.router import get_current_semester_alias
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
import pandas as pd
from .models import EoiApp
from units.models import Unit
from django.contrib.auth import get_user_model
from .serializers import EoiAppSerializer

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

        created = []
        for _, row in df.iterrows():
            unit_code = str(row.get("Unit Code") or "").strip()
            unit_name = str(row.get("Unit Name") or "").strip()
            email = str(row.get("Tutor Email") or "").strip()

            if not unit_code or not email:
                continue

            unit, _ = Unit.objects.get_or_create(unit_code=unit_code, defaults={"unit_name": unit_name})
            tutor, _ = User.objects.get_or_create(email=email, defaults={"username": email.split("@")[0]})

            eoi, _ = EoiApp.objects.update_or_create(
                applicant=tutor,
                unit=unit,
                defaults={
                    "status": "pending",
                    "preference": int(row.get("Preference", 0)),
                    "qualifications": row.get("Qualifications", ""),
                    "availability": row.get("Availability", ""),
                },
            )
            created.append(eoi.id)

        return Response({"created": len(created)}, status=status.HTTP_201_CREATED)

class ApplicantsByUnit(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        unit_id = request.query_params.get("unit_id")
        qs = EoiApp.objects.filter(unit_id=unit_id).order_by("name")
        return Response(EoiAppSerializer(qs, many=True).data)
    
class PreferenceItemSer(serializers.Serializer):
    email = serializers.EmailField()
    preference = serializers.IntegerField(min_value=1, max_value=10)

class SavePreferences(APIView):
    permission_classes = [IsAuthenticated]
    class BodySer(drf_serializers.Serializer):
        unit_id = drf_serializers.IntegerField()
        prefs = drf_serializers.ListField(
            child=drf_serializers.DictField(child=drf_serializers.CharField())
        )
    def post(self, request):
        body = self.BodySer(data=request.data); body.is_valid(raise_exception=True)
        unit_id = body.validated_data["unit_id"]
        updated = 0
        for row in body.validated_data["prefs"]:
            email = row.get("email","").strip().lower()
            pref = int(row.get("preference", 0))
            if not email or not pref: continue
            obj, _ = EoiApp.objects.get_or_create(unit_id=unit_id, email=email)
            obj.preference = pref; obj.save(); updated += 1
        return Response({"updated": updated}, status=status.HTTP_200_OK)