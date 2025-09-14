from .threadlocal import set_view_alias

class SemesterViewAliasMiddleware:
    """
    Reads session key 'view_semester_alias' (set via API) and stores it in threadlocal.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_view_alias(request.session.get("view_semester_alias"))
        return self.get_response(request)
