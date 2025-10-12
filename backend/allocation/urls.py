#allocation/urls.py
from django.urls import path
from .views import (
    AllocationListView,
    ManualAssignView,
    AutoAllocateView,
    ApproveAllocationsView,
    TutorTimetableView,
    SessionsByUnitCode,
    UnitSessionsView,
    UnitsForAllocationView,
    AssignTutorView,
    SuggestTutorsView,
    RunAllocationView,
    TutorSearchView,
    AllocatedTutorEmailsView,
    ListAllTutorsView,
)

urlpatterns = [
    path("run/", RunAllocationView.as_view(), name="allocation-run"),
    path("", AllocationListView.as_view(), name="allocation_list"),
    path("assign-manual/", ManualAssignView.as_view(), name="manual_assign"),
    path("auto/", AutoAllocateView.as_view(), name="auto_allocate"),
    path("approve/", ApproveAllocationsView.as_view(), name="approve_allocations"),
    path("tutor/<int:tutor_id>/", TutorTimetableView.as_view(), name="tutor_timetable"),
    path("sessions/", SessionsByUnitCode.as_view(), name="allocation-sessions"),
    path("units/", UnitsForAllocationView.as_view()),                     # GET ?alias=
    path("unit/<str:unit_code>/sessions/", UnitSessionsView.as_view()),   # GET ?alias=&campus=
    path("suggest_tutors/", SuggestTutorsView.as_view()),                 # GET ?alias=&unit_code=&campus=&q=
    path("assign/", AssignTutorView.as_view(), name="allocation-assign"),
    path("tutor/allocated-emails/", AllocatedTutorEmailsView.as_view(), name="allocated_tutor_emails"),
    path("tutor/search/", TutorSearchView.as_view(), name="tutor_search"),
    path("tutor/list-all/", ListAllTutorsView.as_view(), name="list_all_tutors"),
]
