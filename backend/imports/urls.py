# backend/imports/urls.py
from django.urls import path
from .views import ImportStatusView, UploadImportView, FinalizeEOIView

app_name = "imports"

urlpatterns = [
    path("status/", ImportStatusView.as_view(), name="imports-status"),
    path("finalize/", FinalizeEOIView.as_view(), name="imports-finalize"),
    path("upload/", UploadImportView.as_view(), name="imports-upload"),
]