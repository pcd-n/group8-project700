from django.conf import settings
from .threadlocal import get_view_alias

SEMESTER_APPS = {"units", "timetable", "eoi", "allocation"}

def get_current_semester_alias():
    return getattr(settings, "CURRENT_SEMESTER_ALIAS", None)

class SemesterRouter:
    """
    Route semester apps to the selected semester DB:
    - READS: to session-selected alias if present, else to CURRENT
    - WRITES: always to CURRENT (enforces view-only on old semesters)
    - MIGRATIONS: semester apps migrate only on semester DBs; others only on 'default'
    """
    def db_for_read(self, model, **hints):
        if model._meta.app_label in SEMESTER_APPS:
            return get_view_alias() or get_current_semester_alias()
        return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label in SEMESTER_APPS:
            return get_current_semester_alias()
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in SEMESTER_APPS:
            return db != "default"
        return db == "default"
