from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
from .models import EoiApp
from units.models import Unit
from django.contrib.auth import get_user_model

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
