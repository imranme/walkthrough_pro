from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Observation, Teacher
from .serializers import (
    TeacherSerializer, 
    ObservationReadSerializer, 
    ObservationCreateSerializer, 
    ObservationPatchSerializer
)

# --- Teacher Views ---
class TeacherListCreateView(generics.ListCreateAPIView):
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user).prefetch_related("observations")

class TeacherDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user)

# --- Observation Views (The AI Engine) ---
class ObservationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ObservationCreateSerializer
        return ObservationReadSerializer

    def get_queryset(self):
        return Observation.objects.filter(created_by=self.request.user).select_related("teacher")

# --- Dashboard Stats (Bonus) ---
class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Ekhane amra frontend dashboard card-er jonno data pathai
        teachers = Teacher.objects.filter(created_by=request.user)
        observations = Observation.objects.filter(created_by=request.user)
        
        return Response({
            "total_teachers": teachers.count(),
            "total_observations": observations.count(),
        })