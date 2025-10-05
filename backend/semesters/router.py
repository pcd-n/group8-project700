# backend/semesters/router.py

from django.conf import settings
from .threadlocal import get_view_alias, get_write_alias

# Per-semester data
SEMESTER_APPS = {"units", "timetable", "eoi", "allocation"}

# These must also exist inside each semester DB so FKs can be created there.
# (But at runtime we still use 'default' for these apps.)
DUAL_APPS = {"users", "auth", "contenttypes"}

def get_current_semester_alias():
    return getattr(settings, "CURRENT_SEMESTER_ALIAS", None)

class SemesterRouter:
    """
    Route semester apps to the selected semester DB:
    - READS: to session-selected alias if present, else to CURRENT
    - WRITES: always to CURRENT (view-only on old semesters)
    - MIGRATIONS:
        * semester apps -> only on semester DBs
        * DUAL_APPS (users/auth/contenttypes) -> on BOTH default and semester DBs
        * everything else -> only on 'default'
    """

    # ---------- RUNTIME ----------
    def db_for_read(self, model, **hints):
        if model._meta.app_label in SEMESTER_APPS:
            return get_view_alias() or get_current_semester_alias()
        return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label in SEMESTER_APPS:
            return get_write_alias() or get_current_semester_alias()
        return "default"

    def allow_relation(self, obj1, obj2, **hints): return True

    # ---------- MIGRATIONS ----------
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in DUAL_APPS:
            # allow users/auth/contenttypes to migrate on BOTH default and semester DBs
            return True
        if app_label in SEMESTER_APPS:
            # per-semester apps migrate only on semester DBs
            return db != "default"
        # everything else only on default
        return db == "default"
