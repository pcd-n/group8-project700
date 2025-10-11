from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

ALLOWED_ROLES = ("Admin", "Coordinator")

def _is_admin_or_coord(user):
    if not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    # your User model has has_role()
    return any(user.has_role(r) for r in ALLOWED_ROLES)

@login_required
def unit_details_page(request, code):
    if not _is_admin_or_coord(request.user):
        return HttpResponseForbidden("Forbidden")
    # The page still uses query params (e.g. ?name=...), that’s fine.
    return render(request, "unitdetails.html")

@login_required
def allocation_details_page(request, id=None):
    if not _is_admin_or_coord(request.user):
        return HttpResponseForbidden("Forbidden")
    return render(request, "allocationdetails.html")

@login_required
def allocation_units_page(request):
    if not _is_admin_or_coord(request.user):
        return HttpResponseForbidden("Forbidden")
    return render(request, "allocationunits.html")

@login_required
def users_admin_page(request):
    if not _is_admin_or_coord(request.user):
        return HttpResponseForbidden("Forbidden")
    return render(request, "users_admin.html")
