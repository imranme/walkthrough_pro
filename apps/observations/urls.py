from django.urls import path
from .views import (
    TeacherListCreateView, 
    ObservationListCreateView, 
    DashboardStatsView,
    RecentObservationsView
)

urlpatterns = [
    # Dashboard Cards (24 This Month, 18 Teachers, 3.3 Avg Score)
    # path('dashboard/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard/stats/', DashboardStatsView.as_view()),
    path('dashboard/recent/', RecentObservationsView.as_view()),
    # Teacher Management (Add Teacher & List View)
    path('teachers/', TeacherListCreateView.as_view(), name='teacher-list-create'),

    # Observation Management (Start New Observation & Recent List)
    path('observations/', ObservationListCreateView.as_view(), name='observation-list-create'),
]