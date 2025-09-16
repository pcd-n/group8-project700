from django.contrib import admin
from django.urls import include, path, re_path
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

def health_view(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    # FRONTEND PAGES
    path("", TemplateView.as_view(template_name="index.html")),
    path("home/", TemplateView.as_view(template_name="home.html")),
    path("unitdetails/", TemplateView.as_view(template_name="unitdetails.html"), name="unit_details"),
    path("allocations/<int:id>/", TemplateView.as_view(template_name="allocationdetails.html"), name="alloc_details"),
    path("allocationdetails.html", TemplateView.as_view(template_name="allocationdetails.html")),

    # HEALTH / STATUS (moved off '/')
    path("health/", health_view, name="health"),

    # ADMIN
    path("admin/", admin.site.urls),

    # API DOCS
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # API
    path("api/semesters/", include("semesters.urls")),
    path("api/", include([
        path("users/", include("users.urls")),
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
