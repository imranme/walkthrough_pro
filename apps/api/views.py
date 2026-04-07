from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Observation, Teacher
from .serializers import TeacherSerializer, ObservationReadSerializer, ObservationCreateSerializer

class TeacherListCreateView(generics.ListCreateAPIView):
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user)

class ObservationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    def get_serializer_class(self):
        return ObservationCreateSerializer if self.request.method == "POST" else ObservationReadSerializer
    def get_queryset(self):
        return Observation.objects.filter(created_by=self.request.user).select_related("teacher")

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        # Figma Card Data: Total Teachers, Total Obs, Avg Score
        teachers = Teacher.objects.filter(created_by=request.user)
        obs = Observation.objects.filter(created_by=request.user)
        avg = sum([o.overall_performance_score for o in obs]) / obs.count() if obs.exists() else 0
        return Response({
            "total_teachers": teachers.count(),
            "total_observations": obs.count(),
            "avg_performance": round(avg, 1)
        })