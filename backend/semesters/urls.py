# backend/semesters/urls.py
from django.urls import path
from .views import (
    SemesterListView,
    SemesterCreateView,
    SemesterSelectView,
    SemesterSetCurrentView,
)

app_name = "semesters"

urlpatterns = [
    path("", SemesterListView.as_view(), name="list"),
    path("create/", SemesterCreateView.as_view(), name="create"),
    path("select/", SemesterSelectView.as_view(), name="select-view"),
    path("set-current/<slug:alias>/", SemesterSetCurrentView.as_view(), name="set-current"),
]
