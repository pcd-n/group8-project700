from django.urls import path
from .views import UploadImportView, FinalizeEOIView

app_name = "imports"

urlpatterns = [
    path("finalize/", FinalizeEOIView.as_view(), name="imports-finalize"),
    path("upload/", UploadImportView.as_view(), name="imports-upload"),
]