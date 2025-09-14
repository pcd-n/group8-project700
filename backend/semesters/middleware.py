from .threadlocal import set_view_alias
from .services import hydrate_runtime_databases, is_hydrated

class SemesterViewAliasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._tried_hydrate = False

    def __call__(self, request):
        if not is_hydrated() and not self._tried_hydrate:
            self._tried_hydrate = True
            try:
                hydrate_runtime_databases()
            except Exception:
                pass

        set_view_alias(request.session.get("view_semester_alias"))
        return self.get_response(request)
