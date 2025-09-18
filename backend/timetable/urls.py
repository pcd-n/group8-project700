#timetable/urls.py
from django.urls import path
from .views import sessions_list

urlpatterns = [
    path("sessions/", sessions_list, name="sessions-list"),
]