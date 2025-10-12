#timetable/urls.py
from django.urls import path
from .views import sessions_list, SendEmailWithAttachmentView

urlpatterns = [
    path("sessions/", sessions_list, name="sessions-list"),
    path("utils/send-email/", SendEmailWithAttachmentView.as_view(), name="send_email_with_attachment"),
]