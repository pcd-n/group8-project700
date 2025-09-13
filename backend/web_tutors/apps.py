from django.apps import AppConfig
from django.contrib import admin


class WebTutorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "web_tutors"
    verbose_name = "Web Tutors"

    def ready(self) -> None:
        """Configure admin site when the app is ready"""
        from django.conf import settings

        # Set admin site titles
        admin.site.site_header = getattr(
            settings, "ADMIN_SITE_HEADER", "Web Tutors Administration"
        )
        admin.site.site_title = getattr(
            settings, "ADMIN_SITE_TITLE", "Web Tutors Admin"
        )
        admin.site.index_title = getattr(
            settings, "ADMIN_INDEX_TITLE", "Welcome to Web Tutors Administration"
        )
