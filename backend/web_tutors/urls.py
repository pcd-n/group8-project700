"""
URL configuration for web_tutors project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path, re_path
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from django.conf import settings
from django.conf.urls.static import static

def home_view(request):
    """Simple home view that returns OK status"""
    return JsonResponse({
        "🎓 Project 8 - Tutors Allocation Platform": {
            "status": "✅ RUNNING",
            "message": "Backend API is operational and ready to serve requests!",
            "version": "1.0.0",
            "environment": "Development",
            "timestamp": "2025-09-12"
        },
        "📚 Available API Endpoints": {
            "🏠 Home": "/",
            "👨‍💼 Admin Panel": "/admin/",
            "📖 API Documentation": {
                "Swagger UI": "/api/docs/",
                "ReDoc": "/api/redoc/",
                "OpenAPI Schema": "/api/schema/"
            },
            "🔐 Authentication": "/api/users/",
            "👥 User Management": "/api/users/",
            "📋 Academic Units": "/api/units/",
            "📝 Expression of Interest": "/api/eoi/",
            "📅 Timetable Management": "/api/timetable/",
            "📊 Dashboard": "/api/dashboard/",
            "🔗 Social Auth": "/accounts/"
        },
        "🚀 Quick Start": {
            "1": "Visit /api/docs/ for interactive API documentation",
            "2": "Use /admin/ to access the Django admin panel",
            "3": "Start with /api/users/ for user management",
            "4": "Check /api/schema/ for OpenAPI specification"
        },
        "💡 System Information": {
            "framework": "Django 4.2.23",
            "database": "MariaDB",
            "authentication": "JWT + OAuth2",
            "documentation": "OpenAPI 3.0",
            "features": [
                "User Role Management",
                "Tutor Allocation System", 
                "EOI Processing",
                "Timetable Integration",
                "Multi-Campus Support"
            ]
        }
    }, json_dumps_params={'indent': 2, 'ensure_ascii': False})


urlpatterns = [
    path("", home_view, name="home"),  # Home page showing OK status
    path("admin/", admin.site.urls),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API endpoints - anything appended to api/ will work
    path("api/", include([
        path("users/", include("users.urls")),
        path("units/", include("units.urls")),
        path("eoi/", include("eoi.urls")),
        path("timetable/", include("timetable.urls")),

        # Pham: added path for features
        path("allocation/", include("allocation.urls")), 
        path("imports/", include("imports.urls")),

        path("dashboard/", include("dashboard.urls")),  # Note: using actual directory name "dasboard"
    ])),
     path('accounts/', include('allauth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
