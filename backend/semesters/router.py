# backend/semesters/router.py

from django.conf import settings
from .threadlocal import get_view_alias, get_write_alias
from semesters.state import get_current_alias

# Per-semester data
SEMESTER_APPS = {"eoi", "timetable", "units", "allocation", "imports", "dashboard", "users"}  # include users!

# These must also exist inside each semester DB so FKs can be created there.
# (But at runtime we still use 'default' for these apps.)
DUAL_APPS = {"users", "auth", "contenttypes"}

def get_current_semester_alias():
    return getattr(settings, "CURRENT_SEMESTER_ALIAS", None)

class SemesterRouter:
    def db_for_read(self, model, **hints):
        alias = get_current_alias()
        if model._meta.app_label in SEMESTER_APPS and alias:
            return alias
        # default DB for everything when no alias is active
        return "default"

    def db_for_write(self, model, **hints):
        alias = get_current_alias()
        if model._meta.app_label in SEMESTER_APPS and alias:
            return alias
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        # allow relations within the same DB only
        return hints.get("using") or True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # We want semester apps (including users) created in **all** semester DBs
        # and also in default (so admin users exist there).
        if app_label in SEMESTER_APPS:
            return True  # let your migration command with --database select target
        return None
