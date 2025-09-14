from django.urls import path
from .views import UploadImportView

app_name = "imports"

urlpatterns = [
    path("upload/", UploadImportView.as_view(), name="imports-upload"),
]