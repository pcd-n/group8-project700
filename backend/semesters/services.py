import os
from django.conf import settings
from django.db import connections, OperationalError
from django.core.management import call_command
from .models import Semester

_hydrated_flag = False

def is_hydrated() -> bool:
    return _hydrated_flag

def _mysql_base_conf():
    # Reuse default connection credentials for new DBs
    default = settings.DATABASES["default"]
    return {
        "ENGINE": default["ENGINE"],
        "HOST": default.get("HOST", "127.0.0.1"),
        "PORT": default.get("PORT", "3306"),
        "USER": default["backend"],
        "PASSWORD": default["backend123!"],
        "OPTIONS": default.get("OPTIONS", {}),
    }

def _build_db_settings(db_name: str):
    base = _mysql_base_conf()
    cfg = base | {"NAME": db_name}
    return cfg

def hydrate_runtime_databases():
    """
    Add all known semester DBs into settings.DATABASES.
    Safe to call multiple times; no-ops after first success.
    """
    from django.conf import settings
    global _hydrated_flag
    if _hydrated_flag:
        return

    try:
        for sem in Semester.objects.all():
            settings.DATABASES[sem.alias] = _build_db_settings(sem.db_name)
        current = Semester.objects.filter(is_current=True).first()
        if current:
            settings.CURRENT_SEMESTER_ALIAS = current.alias
        _hydrated_flag = True
    except Exception:
        # Happens during initial migrate when the semesters table doesn't exist yet.
        # We'll try again on the next request.
        _hydrated_flag = False

def create_semester_db(*, year: int, term: str, make_current: bool):
    """
    1) CREATE DATABASE
    2) Register Semester row
    3) Add alias to settings
    4) Run migrations on that alias
    5) Optionally mark as current
    """
    alias = f"sem_{year}_{term.lower()}"
    db_name = f"{settings.SEMESTER_DB_PREFIX}{year}_{term.lower()}"

    # Create schema (using server-level connection)
    default_conn = connections["default"]
    with default_conn.cursor() as c:
        c.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

    # Register semester
    sem, _ = Semester.objects.get_or_create(alias=alias, defaults={"db_name": db_name, "year": year, "term": term})
    settings.DATABASES[alias] = _build_db_settings(db_name)

    # Run migrations on the NEW alias for semester apps
    call_command("migrate", "--database", alias, verbosity=1)

    # Optionally set current
    if make_current:
        Semester.objects.filter(is_current=True).update(is_current=False)
        sem.is_current = True
        sem.save(update_fields=["is_current"])
        settings.CURRENT_SEMESTER_ALIAS = alias

    return sem

def set_view_semester(request, alias: str | None):
    """
    Store the alias user wants to *view*. Writes still go to current per router.
    alias=None resets to current.
    """
    request.session["view_semester_alias"] = alias

def set_current_semester(alias: str):
    Semester.objects.filter(is_current=True).update(is_current=False)
    Semester.objects.filter(alias=alias).update(is_current=True)
    settings.CURRENT_SEMESTER_ALIAS = alias
