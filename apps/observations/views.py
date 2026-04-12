# from rest_framework import generics, permissions, status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from django.utils import timezone
# from django.db.models import Avg
# from .models import Teacher, Observation
# from .serializers import (
#     TeacherSerializer, 
#     ObservationReadSerializer, 
#     ObservationCreateSerializer
# )

# class TeacherListCreateView(generics.ListCreateAPIView):
#     """
#     Handles retrieval of teacher list and creation of new teacher profiles.
#     Associated with the 'Add Teacher' popup in the UI.
#     """
#     serializer_class = TeacherSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         # Only return teachers created by the authenticated user
#         return Teacher.objects.filter(created_by=self.request.user)

#     def perform_create(self, serializer):
#         # Automatically assign the logged-in user as the creator
#         serializer.save(created_by=self.request.user)


# class ObservationListCreateView(generics.ListCreateAPIView):
#     """
#     Manages the two-page observation form workflow.
#     Supports grouped list view with summary statistics.
#     """
#     permission_classes = [permissions.IsAuthenticated]

#     def get_serializer_class(self):
#         # Use specialized serializers for input validation vs. data display
#         if self.request.method == "POST":
#             return ObservationCreateSerializer
#         return ObservationReadSerializer

#     def get_queryset(self):
#         # Optimized query using select_related to fetch teacher details in one go
#         return Observation.objects.filter(created_by=self.request.user).select_related("teacher")

#     def perform_create(self, serializer):
#         # Logic to calculate overall score from the 8 individual slider inputs
#         data = self.request.data
#         scores = [
#             float(data.get('respect_env_score', 0)), float(data.get('culture_learning_score', 0)),
#             float(data.get('classroom_proc_score', 0)), float(data.get('student_behavior_score', 0)),
#             float(data.get('comm_students_score', 0)), float(data.get('questioning_score', 0)),
#             float(data.get('engaging_students_score', 0)), float(data.get('assessment_score', 0))
#         ]
#         avg_score = sum(scores) / len(scores) if scores else 0.0
        
#         # Save with the calculated average and user context
#         return serializer.save(
#             created_by=self.request.user,
#             overall_performance_score=round(avg_score, 1)
#         )

#     def list(self, request, *args, **kwargs):
#         """Returns a list of observations wrapped with a summary object for dashboard cards."""
#         queryset = self.get_queryset()
#         serializer = self.get_serializer(queryset, many=True)
        
#         total = queryset.count()
#         avg = queryset.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
        
#         return Response({
#             "results": serializer.data,
#             "summary": {
#                 "total_observations": total,
#                 "average_score": round(avg, 1) if avg else 0.0
#             }
#         })

#     def create(self, request, *args, **kwargs):
#         """Overridden to return the detailed ReadSerializer format immediately after creation."""
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         instance = self.perform_create(serializer)
#         full_serializer = ObservationReadSerializer(instance)
#         return Response(full_serializer.data, status=status.HTTP_201_CREATED)

#     def get_queryset(self):
#         # টিচারের নাম অনুযায়ী সাজানো থাকবে যাতে ফ্রন্টএন্ডে গ্রুপ করতে সুবিধা হয়
#         return Observation.objects.filter(
#             created_by=self.request.user
#         ).select_related("teacher").order_by('teacher__name', '-created_at')

# class DashboardStatsView(APIView):
#     """
#     Aggregates high-level metrics for the mobile dashboard top cards.
#     """
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         now = timezone.now()

#         # Metrics based on the current authenticated user's data
#         this_month_count = Observation.objects.filter(
#             created_by=user, 
#             created_at__month=now.month,
#             created_at__year=now.year
#         ).count()

#         total_teachers = Teacher.objects.filter(created_by=user).count()

#         avg_perf = Observation.objects.filter(created_by=user).aggregate(
#             Avg('overall_performance_score')
#         )['overall_performance_score__avg']

#         return Response({
#             "this_month_count": this_month_count,
#             "total_teachers": total_teachers,
#             "avg_performance": round(avg_perf, 1) if avg_perf else 0.0
#         })

# class RecentObservationsView(generics.ListAPIView):
#     """
#     ড্যাশবোর্ডের 'Recent Observations' সেকশনের জন্য শুধু সর্বশেষ ৫টি ডাটা দিবে।
#     """
#     serializer_class = ObservationReadSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         # শুধু লগইন করা ইউজারের ডাটা এবং লেটেস্ট ৫টি
#         return Observation.objects.filter(
#             created_by=self.request.user
#         ).select_related("teacher")[:5]

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

# -------------------------------------------------------------------------
# 1. Teacher Management Views
# -------------------------------------------------------------------------

class TeacherListCreateView(generics.ListCreateAPIView):
    """
    Handles retrieval of teacher lists and creation of new teacher profiles.
    Used for the 'Add Teacher' popup and teacher selection dropdowns.
    """
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Returns only teachers created by the authenticated user."""
        return Teacher.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        """Assigns the currently logged-in user as the creator of the teacher profile."""
        serializer.save(created_by=self.request.user)


# -------------------------------------------------------------------------
# 2. Observation Logic & Form Handling
# -------------------------------------------------------------------------

class ObservationListCreateView(generics.ListCreateAPIView):
    """
    Manages the core observation workflow, including the two-page input form.
    Provides a grouped list view for the 'All Observations' screen.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Switch between create-specific validation and read-optimized output."""
        if self.request.method == "POST":
            return ObservationCreateSerializer
        return ObservationReadSerializer

    def get_queryset(self):
        """
        Retrieves all observations for the user.
        Ordered by teacher name and recency for grouped UI display.
        """
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('teacher__name', '-created_at')

    def perform_create(self, serializer):
        """
        Calculates the overall performance score by averaging 8 slider inputs
        before saving the instance.
        """
        data = self.request.data
        score_fields = [
            'respect_env_score', 'culture_learning_score', 'classroom_proc_score', 'student_behavior_score',
            'comm_students_score', 'questioning_score', 'engaging_students_score', 'assessment_score'
        ]
        # Convert inputs to float and calculate mean
        scores = [float(data.get(field, 0)) for field in score_fields]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return serializer.save(
            created_by=self.request.user,
            overall_performance_score=round(avg_score, 1)
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = ObservationReadSerializer(queryset, many=True)
        
        # ১. টোটাল অবজারভেশন সংখ্যা বের করা
        total_obs = queryset.count()
        
        # ২. এভারেজ স্কোর বের করা
        avg_score = queryset.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0

        # ৩. কাস্টম রেসপন্স স্ট্রাকচার তৈরি
        return Response({
            "results": serializer.data,
            "summary": {
                "total_observations": total_obs,
                "average_score": round(avg_score, 1)
            }
        })

    def create(self, request, *args, **kwargs):
        """Overrides default create to return full detail data after a successful POST."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        full_serializer = ObservationReadSerializer(instance)
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)


# -------------------------------------------------------------------------
# 3. AI Results & Detailed Reports
# -------------------------------------------------------------------------

class ObservationDetailView(generics.RetrieveAPIView):
    """
    Retrieves the full analysis of a specific observation.
    This includes AI-generated 'Glow', 'Grow', and T-TESS dimension ratings.
    """
    queryset = Observation.objects.all()
    serializer_class = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        """Ensures users can only access their own detailed observation reports."""
        return Observation.objects.filter(created_by=self.request.user).select_related("teacher")


# -------------------------------------------------------------------------
# 4. Dashboard Analytics & Recent Activity
# -------------------------------------------------------------------------

class DashboardStatsView(APIView):
    """
    Aggregates high-level metrics (KPIs) for the mobile dashboard top cards.
    Calculates monthly activity, teacher reach, and aggregate performance.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # Count observations created in the current calendar month
        this_month_count = Observation.objects.filter(
            created_by=user, 
            created_at__month=now.month,
            created_at__year=now.year
        ).count()

        # Count unique teacher profiles managed by the user
        total_teachers = Teacher.objects.filter(created_by=user).count()

        # Calculate lifetime average performance score
        avg_perf = Observation.objects.filter(created_by=user).aggregate(
            Avg('overall_performance_score')
        )['overall_performance_score__avg']

        return Response({
            "this_month_count": this_month_count,
            "total_teachers": total_teachers,
            "avg_performance": round(avg_perf, 1) if avg_perf else 0.0
        })


class RecentObservationsView(generics.ListAPIView):
    """
    Provides the 'Recent Activity' feed for the dashboard.
    Limited to the 5 most recent observations regardless of teacher.
    """
    serializer_class = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Fetch latest 5 observations using a reverse chronological sort."""
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('-created_at')[:5]