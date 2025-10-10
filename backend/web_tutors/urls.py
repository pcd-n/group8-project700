from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from users.views import roles_list
from .views_pages import (
    unit_details_page,
    allocation_details_page,
    allocation_units_page,
    users_admin_page,
)

def health_view(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    # FRONTEND
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("home/", TemplateView.as_view(template_name="home.html"), name="home"),

    # Pretty pages with role guard
    path("units/<slug:code>/", unit_details_page, name="unit_details"),
    path("allocations/<int:id>/", allocation_details_page, name="alloc_details"),
    path("allocations/", allocation_units_page, name="allocation_units"),

    # (legacy keepers)
    path("unitdetails/", unit_details_page),            # legacy querystring version
    path("allocationdetails/", allocation_details_page),
    # Tutors' timetable page can remain public to authenticated users:
    path("tutors/timetable/", TemplateView.as_view(template_name="tutortimetable.html"),
         name="tutor_timetable"),

    # ADMIN & ACCOUNTS
    path("admin/", admin.site.urls),
    path("api/accounts/", include(('users.urls', 'accounts'), namespace='accounts')),
    path("api/accounts/roles/", roles_list, name="roles_list"),
    path("manage/users", users_admin_page, name="users_admin"),
    path("manage/users/", users_admin_page),

    # API DOCS
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # APP APIs
    path("api/semesters/", include("semesters.urls")),
    path("api/", include([
        path("units/", include("units.urls")),
        path("eoi/", include("eoi.urls")),
        path("timetable/", include("timetable.urls")),
        path("allocation/", include("allocation.urls")),
        path("imports/", include("imports.urls")),
        path("dashboard/", include("dashboard.urls")),
    ])),

    path("accounts/", include("allauth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
