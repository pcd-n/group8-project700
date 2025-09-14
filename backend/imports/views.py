from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .serializers import UploadRequestSerializer, UploadJobSerializer
from .models import UploadJob
from .services import import_eoi_xlsx, import_master_classes_xlsx, import_tutorial_allocations_xlsx

IMPORT_DISPATCH = {
    "eoi": import_eoi_xlsx,
    "master_classes": import_master_classes_xlsx,
    "tutorial_allocations": import_tutorial_allocations_xlsx,
}

class UploadImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = UploadRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        job = UploadJob.objects.create(
            file=s.validated_data["file"],
            import_type=s.validated_data["import_type"],
            created_by=request.user,
        )

        func = IMPORT_DISPATCH[job.import_type]
        # Process immediately (simple sync path)
        with job.file.open("rb") as f:
            func(f, job)

        return Response(UploadJobSerializer(job).data, status=201)
