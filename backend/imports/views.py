<<<<<<< Updated upstream
# imports/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.db import transaction
from django.db.utils import IntegrityError, OperationalError
from django.core.exceptions import ValidationError
from django.utils import timezone

from semesters.threadlocal import force_write_alias
from .serializers import UploadRequestSerializer, UploadJobSerializer
from .models import UploadJob
from .services import IMPORT_DISPATCH
from users.permissions import IsAdminRole
from semesters.services import get_active_semester_alias, ensure_migrated

import logging
logger = logging.getLogger(__name__) 
def _pretty_err(e: Exception) -> str:
    if isinstance(e, ValidationError):
        if getattr(e, "messages", None):
            return "; ".join(map(str, e.messages))
        if getattr(e, "message", None):
            return str(e.message)

    if getattr(e, "args", None):
        return " ".join(str(a) for a in e.args) or str(e)

    return str(e)

class FinalizeEOIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        # CHANGED: resolve + ensure the alias we’re going to touch
        alias = get_active_semester_alias(request)
        logger.info("EOI upload using alias=%s", alias)
        try:
            if alias and alias != "default":
                ensure_migrated(alias)              # NEW: idempotent safety
                with force_write_alias(alias):
                    pass  # nothing else to finalize currently
            return Response({"inserted": 0, "updated": 0}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

class UploadImportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        s = UploadRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        job = UploadJob.objects.create(
            file=s.validated_data["file"],   # job is always on default DB
            import_type=s.validated_data["import_type"],
            created_by=request.user,
        )

        alias = get_active_semester_alias(request)
        logger.info("EOI upload using alias=%s", alias) 
        if not alias or alias == "default":
            return Response({"detail": "No current semester is set."}, status=400)
        ensure_migrated(alias)

        kind = str(job.import_type).lower().strip()
        importer = IMPORT_DISPATCH.get(kind)
        if importer is None:
            return Response({"detail": f"Unsupported import type '{kind}'."}, status=400)

        try:
            with job.file.open("rb") as f, force_write_alias(alias), transaction.atomic(using=alias, savepoint=False):
                result = importer(f, job, using=alias)

            job.finished_at = timezone.now()
            job.save(update_fields=["finished_at"])

            return Response(
                {"ok": True, "result": result, "job": UploadJobSerializer(job).data},
                status=201,
            )

        except (ValidationError, IntegrityError, OperationalError) as e:
            return Response({"detail": _pretty_err(e)}, status=400)

        except Exception as e:
            return Response({"detail": _pretty_err(e)}, status=400)
=======
# imports/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.db import transaction
from django.db.utils import IntegrityError, OperationalError
from django.core.exceptions import ValidationError
from django.utils import timezone

from semesters.router import get_current_semester_alias
from semesters.threadlocal import force_write_alias
from .serializers import UploadRequestSerializer, UploadJobSerializer
from .models import UploadJob
from .services import IMPORT_DISPATCH
from users.permissions import IsAdminRole

def _pretty_err(e: Exception) -> str:
    if isinstance(e, ValidationError):
        if getattr(e, "messages", None):
            return "; ".join(map(str, e.messages))
        if getattr(e, "message", None):
            return str(e.message)

    if getattr(e, "args", None):
        return " ".join(str(a) for a in e.args) or str(e)

    return str(e)

class FinalizeEOIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        alias = request.query_params.get("alias") or get_current_semester_alias()
        try:
            if alias:
                with force_write_alias(alias):
                    pass # nothing else to finalize currently
            return Response({"inserted": 0, "updated": 0}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

class UploadImportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

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

            job.finished_at = timezone.now()
            job.save(update_fields=["finished_at"])

            return Response(
                {"ok": True, "result": result, "job": UploadJobSerializer(job).data},
                status=201,
            )
        
        except (ValidationError, IntegrityError, OperationalError) as e:
            return Response({"detail": _pretty_err(e)}, status=400)

        except Exception as e:
            return Response({"detail": _pretty_err(e)}, status=400)
>>>>>>> Stashed changes
