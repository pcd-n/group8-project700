from django.urls import path
from .views import (
    AllocationListView,
    ManualAssignView,
    AutoAllocateView,
    ApproveAllocationsView,
    TutorTimetableView,
)

urlpatterns = [
    path("", AllocationListView.as_view(), name="allocation_list"),
    path("assign/", ManualAssignView.as_view(), name="manual_assign"),
    path("auto/", AutoAllocateView.as_view(), name="auto_allocate"),
    path("approve/", ApproveAllocationsView.as_view(), name="approve_allocations"),
    path("tutor/<int:tutor_id>/", TutorTimetableView.as_view(), name="tutor_timetable"),
]
