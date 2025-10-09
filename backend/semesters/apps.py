from django.apps import AppConfig

class SemestersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "semesters"

    def ready(self):
        from .services import hydrate_runtime_databases
        try:
            hydrate_runtime_databases()
        except Exception:
            # During initial migrate the semesters table may not exist yet.
            pass