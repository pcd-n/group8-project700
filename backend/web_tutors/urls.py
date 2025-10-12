# backend/web_tutors/urls.py
from django.contrib import admin
from django.urls import include, path, re_path
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from users.views import roles_list

def health_view(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    # FRONTEND PAGES
    path("", TemplateView.as_view(template_name="index.html")),
    path("home/", TemplateView.as_view(template_name="home.html")),

    path("tutor-search/", TemplateView.as_view(template_name="tutor_search.html"), name="tutor_search"),
    path("tutor-list/", TemplateView.as_view(template_name="tutor_list.html"), name="tutor_list"),
    # Pretty Unit + Allocation pages
    # e.g. /units/KIT101/ or /units/KIT101/?name=Programming%20Fundamentals
    path("api/accounts/roles/", roles_list, name="roles_list"),
    path("units/<slug:code>/", TemplateView.as_view(template_name="unitdetails.html"), name="unit_details"),
    path("allocations/<int:id>/", TemplateView.as_view(template_name="allocationdetails.html"), name="alloc_details"),

    # (Optional legacy) keep these only while migrating old links
    path("unitdetails/", TemplateView.as_view(template_name="unitdetails.html")),          # legacy querystring version
    path("allocations/", TemplateView.as_view(template_name="allocationunits.html"), name="allocation_units"),
    path("allocationdetails/", TemplateView.as_view(template_name="allocationdetails.html"), name="allocation_details"),  # querystring style

    path("tutors/timetable/", TemplateView.as_view(template_name="tutortimetable.html"), name="tutor_timetable"),

    # HEALTH
    path("health/", health_view, name="health"),

    # DJANGO ADMIN
    path("admin/", admin.site.urls),
    
    # Accounts / Users (API + pretty Users page)
    path("api/accounts/", include(('users.urls', 'accounts'), namespace='accounts')),
    path("api/accounts/roles/", roles_list, name="roles_list"),
    
    # Pretty management page for Users (now served by Django instead of Apache 404)
    path("manage/users",  TemplateView.as_view(template_name="users_admin.html"), name="users_admin"),
    path("manage/users/", TemplateView.as_view(template_name="users_admin.html")),
    
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

    # Allauth (if you use it)
    path("accounts/", include("allauth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
