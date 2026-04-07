from django.urls import path
from .views import (
    TeacherListCreateView,
    TeacherDetailView,
    ObservationListCreateView,
    ObservationDetailView,
    DashboardStatsView,
)

urlpatterns = [
    path("teachers/", TeacherListCreateView.as_view(), name="teacher-list"),
    path("teachers/<int:pk>/", TeacherDetailView.as_view(), name="teacher-detail"),
    path("observations/", ObservationListCreateView.as_view(), name="observation-list"),
    path("observations/<int:pk>/", ObservationDetailView.as_view(), name="observation-detail"),
    path("dashboard/", DashboardStatsView.as_view(), name="dashboard-stats"),
]