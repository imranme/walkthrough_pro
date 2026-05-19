from django.urls import path
from .views import (
    TeacherListCreateView, 
    ObservationListCreateView, 
    ObservationDetailView,\
    RewriteReportView,
    DashboardStatsView,
    RecentObservationsView,
    DomainAnalyticsView,
    TeacherSimpleListView
)

urlpatterns = [
    # Dashboard Stats
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard/recent/', RecentObservationsView.as_view(), name='dashboard-recent'),
    
    # Teacher Management
    path('teachers/', TeacherListCreateView.as_view(), name='teacher-list-create'),

    # Observation Management (এটাই এখন মেইন এপিআই, যেখানে AI কাজ করবে)
    path('observations/', ObservationListCreateView.as_view(), name='observation-list-create'),
    path('observations/<int:pk>/', ObservationDetailView.as_view(), name='observation-detail'),

    path('observations/<int:pk>/rewrite/', RewriteReportView.as_view(), name='observation-rewrite'),

    # Analytics & Graphs
    path('analytics/', DomainAnalyticsView.as_view(), name='domain-analytics'),
    
    # Recent Observations
    path('recent/', RecentObservationsView.as_view(), name='recent-observations'),

    #theachers list
    path('teachers/names/', TeacherSimpleListView.as_view(), name='teacher-names-list'),

]