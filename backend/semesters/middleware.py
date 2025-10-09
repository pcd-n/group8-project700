from django.conf import settings
import logging
from .services import hydrate_runtime_databases, ensure_current_semester_alias, _register_alias
from .models import Semester

log = logging.getLogger(__name__)

AUTH_FREE_PREFIXES = (
    "/api/users/token",
    "/api/users/register",
    "/api/users/token/refresh",
)

class SemesterViewAliasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        p = request.path.rstrip("/")
        if any(p.startswith(pref) for pref in AUTH_FREE_PREFIXES):
            return self.get_response(request)

        try:
            # Keep whatever you already do here (e.g., read current semester,
            # set settings.CURRENT_SEMESTER_ALIAS, etc.)
            from .services import ensure_current_semester_alias  # or your function
            ensure_current_semester_alias()
        except Exception as e:
            # Fall back so login, docs, etc. keep working
            log.warning("Semester alias middleware fallback to 'default': %s", e)
            settings.CURRENT_SEMESTER_ALIAS = "default"

        return self.get_response(request)

class SemesterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ensure aliases exist and the current semester alias is registered/prewarmed
        hydrate_runtime_databases()
        alias = ensure_current_semester_alias()  # registers & sets settings.CURRENT_SEMESTER_ALIAS
        return self.get_response(request)