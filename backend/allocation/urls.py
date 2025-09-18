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
    path("assign/", AssignTutorView.as_view()),
]
