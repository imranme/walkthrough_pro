from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Teacher, Observation
from .serializers import TeacherSerializer, ObservationCreateSerializer, ObservationReadSerializer

# --- Teacher Views ---
class TeacherListCreateView(generics.ListCreateAPIView):
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user)

class TeacherDetailView(generics.RetrieveUpdateDestroyAPIView): # <--- EI CLASS TI MISSING CHILO
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user)

# --- Observation Views ---
class ObservationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return ObservationCreateSerializer if self.request.method == "POST" else ObservationReadSerializer

    def get_queryset(self):
        # order_by('-created_at') dile shobar shesh-er observation shobar age dekhabe
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('-created_at')

# --- Dashboard Stats ---
class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        teachers = Teacher.objects.filter(created_by=request.user)
        obs = Observation.objects.filter(created_by=request.user)
        avg = sum([o.overall_performance_score for o in obs]) / obs.count() if obs.exists() else 0.0
        return Response({
            "total_teachers": teachers.count(),
            "total_observations": obs.count(),
            "avg_performance": round(avg, 1) 
        })