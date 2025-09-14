from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from imports.models import UploadJob
from imports.services import import_eoi_xlsx

class Command(BaseCommand):
    help = "Import EOI spreadsheet (.xlsx) into eoi_app (SCD-II)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)

    def handle(self, *args, **opts):
        path = opts["file"]
        job = UploadJob.objects.create(import_type="eoi")
        with open(path, "rb") as f:
            import_eoi_xlsx(f, job)
        self.stdout.write(self.style.SUCCESS(f"EOI import done: ok={job.rows_ok}, err={job.rows_error}"))
