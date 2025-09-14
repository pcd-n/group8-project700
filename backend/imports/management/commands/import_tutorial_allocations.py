from django.core.management.base import BaseCommand
from imports.models import UploadJob
from imports.services import import_tutorial_allocations_xlsx

class Command(BaseCommand):
    help = "Import Tutorial Allocations (.xlsx) into timetable slots."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)

    def handle(self, *args, **opts):
        job = UploadJob.objects.create(import_type="tutorial_allocations")
        with open(opts["file"], "rb") as f:
            import_tutorial_allocations_xlsx(f, job)
        self.stdout.write(self.style.SUCCESS(f"Tutorial allocations import: ok={job.rows_ok}, err={job.rows_error}"))
