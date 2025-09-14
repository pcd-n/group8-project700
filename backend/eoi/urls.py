from django.urls import path
from .views import EOIUploadView, ApplicantsByUnit, SavePreferences

urlpatterns = [
    path("upload/", EOIUploadView.as_view(), name="eoi-upload"),
    path("applicants/", ApplicantsByUnit.as_view(), name="eoi-applicants"),
    path("preferences/", SavePreferences.as_view(), name="eoi-preferences"),
]