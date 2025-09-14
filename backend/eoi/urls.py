from django.urls import path
from .views import EOIUploadView

urlpatterns = [
    path("upload/", EOIUploadView.as_view(), name="eoi-upload"),
]