from django.core.management.base import BaseCommand
from imports.models import UploadJob
from imports.services import import_master_classes_xlsx

class Command(BaseCommand):
    help = "Import Master Class List (.xlsx) into master_class_time."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)

    def handle(self, *args, **opts):
        job = UploadJob.objects.create(import_type="master_classes")
        with open(opts["file"], "rb") as f:
            import_master_classes_xlsx(f, job)
        self.stdout.write(self.style.SUCCESS(f"Master classes import: ok={job.rows_ok}, err={job.rows_error}"))
