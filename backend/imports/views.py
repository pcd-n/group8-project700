from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db import transaction
from semesters.router import get_current_semester_alias

from .serializers import UploadRequestSerializer, UploadJobSerializer
from .models import UploadJob
from .services import import_eoi_xlsx, import_master_classes_xlsx, import_tutorial_allocations_xlsx

IMPORT_DISPATCH = {
    "eoi": import_eoi_xlsx,
    "master_classes": import_master_classes_xlsx,
    "tutorial_allocations": import_tutorial_allocations_xlsx,
}

class UploadImportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]  # only admins should upload
    def post(self, request):
        s = UploadRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        job = UploadJob.objects.create(
            file=s.validated_data["file"],
            import_type=s.validated_data["import_type"],
            created_by=request.user,
        )

        func = IMPORT_DISPATCH[job.import_type]
        alias = get_current_semester_alias()

        with job.file.open("rb") as f, transaction.atomic(using=alias):
            func(f, job, using=alias)  # pass alias down

        return Response(UploadJobSerializer(job).data, status=201)