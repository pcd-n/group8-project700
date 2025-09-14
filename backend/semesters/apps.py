from django.apps import AppConfig

class SemestersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "semesters"

    def ready(self):
        # At startup, load configured semester DB connections into Django
        from .services import hydrate_runtime_databases
        try:
            hydrate_runtime_databases()
        except Exception:
            pass
