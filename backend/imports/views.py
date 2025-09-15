# imports/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from django.db import transaction
from django.db.utils import IntegrityError, OperationalError
from django.core.exceptions import ValidationError

from semesters.router import get_current_semester_alias
from semesters.threadlocal import force_write_alias
from .serializers import UploadRequestSerializer, UploadJobSerializer
from .models import UploadJob
from .services import IMPORT_DISPATCH 

def _pretty_err(e: Exception) -> str:
    if hasattr(e, "args") and len(e.args) >= 2 and isinstance(e.args[1], str):
        return e.args[1]
    return getattr(e, "message", None) or " ".join(str(a) for a in getattr(e, "args", ())) or str(e)

class UploadImportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        s = UploadRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        job = UploadJob.objects.create(
            file=s.validated_data["file"],   # job is always on default DB
            import_type=s.validated_data["import_type"],
            created_by=request.user,
        )

        alias = get_current_semester_alias()
        if not alias:
            return Response({"detail": "No current semester is set."}, status=400)

        kind = str(job.import_type).lower().strip()
        importer = IMPORT_DISPATCH.get(kind)
        if importer is None:
            return Response({"detail": f"Unsupported import type '{kind}'."}, status=400)

        try:
            with job.file.open("rb") as f, force_write_alias(alias), transaction.atomic(using=alias, savepoint=False):
                result = importer(f, job, using=alias)


            job.status = "finished"
            job.error = ""
            job.save(update_fields=["status", "error"])
            return Response({"ok": True, "result": result, "job": UploadJobSerializer(job).data}, status=201)

        except (ValidationError, IntegrityError, OperationalError) as e:
            return Response({"detail": _pretty_err(e)}, status=400)

        except Exception as e:
            return Response({"detail": _pretty_err(e)}, status=400)