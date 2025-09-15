import copy
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from .models import Semester

_hydrated_flag = False

def is_hydrated() -> bool:
    return _hydrated_flag

# ---- helpers to inherit full DB settings and register aliases safely ----

_DB_KEYS_TO_COPY = (
    "ENGINE", "HOST", "PORT", "USER", "PASSWORD", "OPTIONS",
    "AUTOCOMMIT", "ATOMIC_REQUESTS", "CONN_MAX_AGE",
    "CONN_HEALTH_CHECKS", "TIME_ZONE", "TEST", "MIRROR",
)

def _base_from_default():
    """
    Make a dict that mirrors the default DB settings **including**
    ATOMIC_REQUESTS and other flags, so Django's per-request atomic wrapper
    won't KeyError when it iterates over all databases.
    """
    default = settings.DATABASES["default"]
    base = {}
    for k in _DB_KEYS_TO_COPY:
        if k in default:
            base[k] = copy.deepcopy(default[k])
    return base

def _build_db_settings(db_name: str):
    base = _base_from_default()
    base["NAME"] = db_name
    return base

def _db_exists(db_name: str) -> bool:
    # check against information_schema using the default connection
    with connections["default"].cursor() as c:
        c.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name=%s",
            [db_name],
        )
        return c.fetchone() is not None

def list_existing_semesters():
    """Return Semester rows whose MySQL schema exists."""
    from .models import Semester  # local import to avoid cycles
    existing = []
    for s in Semester.objects.all():
        if _db_exists(s.db_name):
            existing.append(s)
    return existing

def _register_alias(alias: str, db_name: str):
    """
    Put the alias into settings.DATABASES and **force Django to create
    a Connection** so its internal defaults are applied.
    """
    settings.DATABASES[alias] = _build_db_settings(db_name)
    # Touching connections[alias] makes Django normalize settings and
    # attach defaults so code like BaseHandler.make_view_atomic won't KeyError.
    _ = connections[alias]

def hydrate_runtime_databases():
    """
    Add all known semester DBs into settings.DATABASES.
    Safe to call multiple times; no-ops after first success.
    """
    global _hydrated_flag
    if _hydrated_flag:
        return

    try:
        for sem in Semester.objects.all():
            _register_alias(sem.alias, sem.db_name)
        current = Semester.objects.filter(is_current=True).first()
        if current:
            settings.CURRENT_SEMESTER_ALIAS = current.alias
        _hydrated_flag = True
    except Exception:
        # Happens during initial migrate when the semesters table doesn't exist yet.
        _hydrated_flag = False

def ensure_current_semester_alias():
    """
    Ensure settings.CURRENT_SEMESTER_ALIAS is set and the alias is registered.
    Used by middleware on each request.
    """
    alias = getattr(settings, "CURRENT_SEMESTER_ALIAS", None)
    if alias:
        return alias
    current = Semester.objects.filter(is_current=True).first()
    if current:
        _register_alias(current.alias, current.db_name)
        settings.CURRENT_SEMESTER_ALIAS = current.alias
        return current.alias
    return None

# ---- auth check for creator ----

def _actor_is_admin(actor) -> bool:
    if not actor or not getattr(actor, "is_authenticated", False):
        return False
    if getattr(actor, "is_superuser", False) or getattr(actor, "is_staff", False):
        return True
    try:
        if actor.has_perm("semesters.add_semester"):
            return True
        if actor.groups.filter(name__iexact="Admin").exists():
            return True
    except Exception:
        pass
    return False

# ---- main entry points ----

def create_semester_db(*, year: int, term: str, make_current: bool, actor=None):
    """
    1) Authorize (only admins)
    2) CREATE DATABASE
    3) Create/lookup Semester row
    4) Register alias (with full settings) and pre-warm connection
    5) Run migrations on that alias (semester apps only via router)
    6) Optionally mark as current
    """
    if actor is not None and not _actor_is_admin(actor):
        raise PermissionDenied("Only admin users can create a new semester database.")

    alias = f"sem_{year}_{term.lower()}"
    db_name = f"{settings.SEMESTER_DB_PREFIX}{year}_{term.lower()}"

    # 2) Create schema on server
    default_conn = connections["default"]
    try:
        with default_conn.cursor() as c:
            c.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
    except OperationalError as e:
        raise PermissionDenied(
            f"Database user '{settings.DATABASES['default']['USER']}' "
            f"does not have permission to create `{db_name}`. "
            f"Grant CREATE/ALL on `{settings.SEMESTER_DB_PREFIX}%`.* and try again."
        ) from e

    # 3) Register semester row (on default DB)
    sem, _ = Semester.objects.get_or_create(
        alias=alias,
        defaults={"db_name": db_name, "year": year, "term": term},
    )

    # 4) Register alias and pre-warm the connection so defaults exist
    _register_alias(alias, db_name)

    # 5) Migrate this alias (router will send only semester apps here)
    call_command("migrate", "contenttypes", database=alias, verbosity=1)
    call_command("migrate", "auth",         database=alias, verbosity=1)
    call_command("migrate", "users",        database=alias, verbosity=1)
    call_command("migrate", database=alias, verbosity=1)
    # 6) Optionally mark as current
    if make_current:
        Semester.objects.filter(is_current=True).update(is_current=False)
        sem.is_current = True
        sem.save(update_fields=["is_current"])
        settings.CURRENT_SEMESTER_ALIAS = alias

    return sem

def set_view_semester(request, alias: str | None):
    request.session["view_semester_alias"] = alias

def set_current_semester(alias: str):
    Semester.objects.filter(is_current=True).update(is_current=False)
    Semester.objects.filter(alias=alias).update(is_current=True)
    settings.CURRENT_SEMESTER_ALIAS = alias
