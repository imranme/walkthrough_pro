from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg
from .models import Teacher, Observation
from .serializers import (
    TeacherSerializer, 
    ObservationReadSerializer, 
    ObservationCreateSerializer
)

class TeacherListCreateView(generics.ListCreateAPIView):
    """
    Handles Listing and Creating Teachers.
    """
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ObservationListCreateView(generics.ListCreateAPIView):
    """
    Handles Observation creation and listing with detailed response.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Validation er jonno CreateSerializer, data show korar jonno ReadSerializer
        return ObservationCreateSerializer if self.request.method == "POST" else ObservationReadSerializer

    def get_queryset(self):
        # select_related('teacher') optimizes the query for teacher details
        return Observation.objects.filter(created_by=self.request.user).select_related("teacher")

    def perform_create(self, serializer):
        # Save observation and link it to the logged-in user
        return serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Overriding create to return detailed ObservationReadSerializer data 
        immediately after a successful POST request.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # KEY FIX: Saving to an instance variable to avoid 'KeyError: id'
        instance = self.perform_create(serializer)
        
        # Return full details (Teacher name, Grade level, Subject, Formatted Date/Time)
        full_serializer = ObservationReadSerializer(instance)
        
        headers = self.get_success_headers(serializer.data)
        return Response(full_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DashboardStatsView(APIView):
    """
    Provides statistics for the Dashboard cards (This Month, Total Teachers, Avg Score).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # Figma Card: Observations this month
        this_month_count = Observation.objects.filter(
            created_by=user, 
            created_at__month=now.month,
            created_at__year=now.year
        ).count()

        # Figma Card: Total Teachers unique to the user
        total_teachers = Teacher.objects.filter(created_by=user).count()

        # Figma Card: Average Performance Score across all observations
        avg_perf = Observation.objects.filter(created_by=user).aggregate(
            Avg('overall_performance_score')
        )['overall_performance_score__avg']

        return Response({
            "this_month_count": this_month_count,
            "total_teachers": total_teachers,
            "avg_performance": round(avg_perf, 1) if avg_perf else 0.0
        })