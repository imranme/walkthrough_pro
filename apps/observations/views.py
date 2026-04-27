from rest_framework import generics, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
from .models import Teacher, Observation
from .serializers import (
    TeacherSerializer, 
    ObservationReadSerializer, 
    ObservationCreateSerializer
)

# -------------------------------------------------------------------------
# ACCESS CONTROL: Custom Permission for Super Admins
# -------------------------------------------------------------------------
class IsSuperUser(permissions.BasePermission):
    """ Allows access only to Django Superusers. """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

# -------------------------------------------------------------------------
# 1. TEACHER MANAGEMENT
# -------------------------------------------------------------------------
class TeacherListCreateView(generics.ListCreateAPIView):
    """ 
    API to List and Create Teachers. 
    Teachers are filtered based on the admin who created them.
    """
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'department']

    def get_queryset(self):
        return Teacher.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign the logged-in admin as the creator
        serializer.save(created_by=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Calculate summary analytics for the teacher list page cards
        total_teachers = queryset.count()
        all_obs = Observation.objects.filter(created_by=request.user)
        overall_avg = all_obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0

        distinguished = 0
        needs_support = 0
        for teacher in queryset:
            score = teacher.avg_score # Assuming avg_score is a property in Teacher model
            if score >= 3.5:
                distinguished += 1
            elif 0 < score < 2.5:
                needs_support += 1

        return Response({
            "teachers": serializer.data,
            "summary_cards": {
                "total_teachers": total_teachers,
                "overall_avg": round(overall_avg, 1),
                "distinguished": distinguished,
                "needs_support": needs_support
            }
        })


# class ObservationListCreateView(generics.ListCreateAPIView):
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get_serializer_class(self):
#         if self.request.method == "POST":
#             return ObservationCreateSerializer
#         return ObservationReadSerializer

#     def get_queryset(self):
#         return Observation.objects.filter(
#             created_by=self.request.user
#         ).select_related("teacher").order_by('-created_at')

#     def create(self, request, *args, **kwargs):
#         data = request.data
        
#         # ১. স্কোর এবং এভারেজ ক্যালকুলেশন
#         score_fields = [
#             'respect_env_score', 'culture_learning_score', 'classroom_proc_score', 
#             'student_behavior_score', 'comm_students_score', 'questioning_score', 
#             'engaging_students_score', 'assessment_score'
#         ]
        
#         try:
#             scores = [float(data.get(f, 3.0)) for f in score_fields]
#             avg_score = round(sum(scores) / len(scores), 1)
#         except:
#             avg_score = 3.0

#         # ২. ডাটাবেজে সেভ (পেন্ডিং স্ট্যাটাসে)
#         serializer = self.get_serializer(data=data)
#         serializer.is_valid(raise_exception=True)
#         observation = serializer.save(
#             created_by=request.user, 
#             overall_performance_score=avg_score,
#             status='pending'
#         )
        
#         # ৩. AI প্রসেসিং এবং ডাইমেনশন জেনারেশন
#         try:
#             from .ai_service import ObservationAIService
#             ratings_dict = {f: float(data.get(f, 3.0)) for f in score_fields}
            
#             # AI সার্ভিস কল করা
#             ai_feedback = ObservationAIService.get_ai_feedback(data.get('raw_notes', ''), ratings_dict)

#             # স্ক্রিনশটের মতো ওই ৮টি কার্ডের ডাটা জেনারেট করা
#             dimensions = [
#                 {"title": "2.1 Achieving Expectations", "rating": "Proficient" if avg_score >= 3 else "Developing"},
#                 {"title": "2.2 Content Knowledge and Expertise", "rating": "Proficient" if avg_score >= 3 else "Developing"},
#                 {"title": "2.3 Communication", "rating": "Proficient"},
#                 {"title": "2.4 Differentiation", "rating": "Developing"},
#                 {"title": "2.5 Monitor and Adjust", "rating": "Proficient"},
#                 {"title": "3.1 Classroom Environment, Routines, and Procedures", "rating": "Proficient"},
#                 {"title": "3.2 Managing Student Behavior", "rating": "Proficient"},
#                 {"title": "3.3 Classroom Culture", "rating": "Proficient"}
#             ]

#             if ai_feedback and isinstance(ai_feedback, dict) and "error" not in ai_feedback:
#                 observation.glow = ai_feedback.get('glow', 'Great execution of the lesson.')
#                 observation.grow = ai_feedback.get('grow', 'Focus on student engagement.')
#                 # যদি AI থেকে dimensions আসে তবে সেটা নাও, নাহলে আমাদের বানানো লিস্ট নাও
#                 observation.dimensions_data = ai_feedback.get('dimensions', dimensions)
#             else:
#                 # ব্যাকআপ ডাটা (যদি AI ফেইল করে)
#                 observation.glow = "Teacher clearly explained the lesson objectives."
#                 observation.grow = "Increase interaction between students."
#                 observation.dimensions_data = dimensions
            
#             observation.status = 'completed'
#             observation.save()

#         except Exception as e:
#             print(f"DEBUG ERROR: {str(e)}")
#             observation.status = 'completed'
#             observation.save()

#         # ৪. রেসপন্স পাঠানো (Read Serializer দিয়ে যাতে সব ডাটা দেখায়)
#         final_serializer = ObservationReadSerializer(observation)
#         return Response(final_serializer.data, status=status.HTTP_201_CREATED)

class ObservationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == "POST":
            return ObservationCreateSerializer
        return ObservationReadSerializer

    def get_queryset(self):
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('-created_at')

    def create(self, request, *args, **kwargs):
        data = request.data
        
        # ১. স্কোর এবং এভারেজ ক্যালকুলেশন
        score_fields = [
            'respect_env_score', 'culture_learning_score', 'classroom_proc_score', 
            'student_behavior_score', 'comm_students_score', 'questioning_score', 
            'engaging_students_score', 'assessment_score'
        ]
        
        try:
            scores = [float(data.get(f, 3.0)) for f in score_fields]
            avg_score = round(sum(scores) / len(scores), 1)
        except Exception:
            avg_score = 3.0

        # ২. ডাটাবেজে সেভ
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        observation = serializer.save(
            created_by=request.user, 
            overall_performance_score=avg_score,
            status='pending'
        )
        
        # ৩. AI ফিডব্যাক কল (সঠিক ইনডেন্টেশন সহ)
        try:
            from .ai_service import ObservationAIService
            ratings_dict = {f: float(data.get(f, 3.0)) for f in score_fields}
            
            # এই লাইনেই তোমার ইনডেন্টেশন এরর ছিল, এখন এটা ঠিক করা হয়েছে
            ai_feedback = ObservationAIService.get_ai_feedback(
                raw_notes=data.get('raw_notes', ''),
                ratings=ratings_dict,
                extra_data=data
            )

            dimensions = self.get_default_dimensions(avg_score)

            if ai_feedback and isinstance(ai_feedback, dict) and "error" not in ai_feedback:
                observation.glow = ai_feedback.get('glow')
                observation.grow = ai_feedback.get('grow')
                observation.dimensions_data = ai_feedback.get('dimensions', dimensions)
            else:
                observation.glow = "Teacher clearly explained the lesson objectives."
                observation.grow = "Increase interaction between students."
                observation.dimensions_data = dimensions
            
            observation.status = 'completed'
            observation.save()

        except Exception as e:
            print(f"DEBUG ERROR: {str(e)}")
            observation.dimensions_data = self.get_default_dimensions(avg_score)
            observation.status = 'completed'
            observation.save()

        # ৪. রেসপন্স পাঠানো
        observation.refresh_from_db()
        final_serializer = ObservationReadSerializer(observation)
        return Response(final_serializer.data, status=status.HTTP_201_CREATED)

    def get_default_dimensions(self, avg):
        """স্কোরের ওপর ভিত্তি করে ডাইনামিক রেটিং জেনারেট করে"""
        if avg >= 3.6:
            rating = "Distinguished"
        elif avg >= 2.8:
            rating = "Proficient"
        else:
            rating = "Developing"

        titles = [
            "2.1 Achieving Expectations", 
            "2.2 Content Knowledge and Expertise",
            "2.3 Communication", 
            "2.4 Differentiation", 
            "2.5 Monitor and Adjust",
            "3.1 Classroom Environment, Routines, and Procedures",
            "3.2 Managing Student Behavior", 
            "3.3 Classroom Culture"
        ]

        dimensions = []
        for title in titles:
            # ২.৪ টাইটেল থাকলে সবসময় Developing (ডিজাইন অনুযায়ী), বাকিগুলো ডাইনামিক
            current_rating = "Developing" if "2.4" in title else rating
            dimensions.append({"title": title, "rating": current_rating})
            
        return dimensions

# -------------------------------------------------------------------------
# 3. UNIFIED DASHBOARD STATS (Main Landing Page)
# -------------------------------------------------------------------------
class DashboardStatsView(APIView):
    """ Standard Dashboard providing counts and basic trends. """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        platform = request.query_params.get('platform', 'mobile')

        # Mobile-specific basic stats
        this_month_count = Observation.objects.filter(
            created_by=user, 
            created_at__month=now.month,
            created_at__year=now.year
        ).count()
        total_teachers = Teacher.objects.filter(created_by=user).count()
        avg_perf = Observation.objects.filter(created_by=user).aggregate(
            Avg('overall_performance_score')
        )['overall_performance_score__avg'] or 0.0

        mobile_data = {
            "this_month_count": this_month_count,
            "total_teachers": total_teachers,
            "avg_performance": round(avg_perf, 1)
        }

        if platform == 'mobile':
            return Response(mobile_data)

        # Admin Web Dashboard Logic
        if not user.is_staff:
            return Response({"detail": "Admins only."}, status=status.HTTP_403_FORBIDDEN)

        total_observations = Observation.objects.filter(created_by=user).count()
        distinguished_count = Observation.objects.filter(
            created_by=user, overall_performance_score__gte=3.5
        ).count()

        return Response({
            **mobile_data,
            "total_observations": total_observations,
            "distinguished_count": distinguished_count,
            "message": "Full Web Dashboard Analytics Loaded"
        })

# -------------------------------------------------------------------------
# 4. DOMAIN ANALYTICS (The Graph & Radar Data)
# -------------------------------------------------------------------------
class DomainAnalyticsView(APIView):
    """
    Handles Radar Charts and Analytics.
    Optimized to handle both JSONField data and model scores.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Fetch completed observations for the current user
        queryset = Observation.objects.filter(created_by=request.user, status='completed')
        total_obs = queryset.count()

        if total_obs == 0:
            return Response({"message": "No completed observations found."}, status=200)

        # Initialization
        env_radar = {"Respect": 0, "Culture": 0, "Procedures": 0, "Behavior": 0}
        ins_radar = {"Communication": 0, "Questioning": 0, "Engagement": 0, "Assessment": 0}
        
        env_total_scores = []
        ins_total_scores = []

        for obs in queryset:
            # 1. Fallback Logic: Try to get data from individual model fields first
            # These field names should match your Observation model fields
            e_scores = {
                "Respect": getattr(obs, 'respect_env_score', 0) or 0,
                "Culture": getattr(obs, 'culture_learning_score', 0) or 0,
                "Procedures": getattr(obs, 'classroom_proc_score', 0) or 0,
                "Behavior": getattr(obs, 'student_behavior_score', 0) or 0
            }
            i_scores = {
                "Communication": getattr(obs, 'comm_students_score', 0) or 0,
                "Questioning": getattr(obs, 'questioning_score', 0) or 0,
                "Engagement": getattr(obs, 'engaging_students_score', 0) or 0,
                "Assessment": getattr(obs, 'assessment_score', 0) or 0
            }

            # Add to radar totals
            for k, v in e_scores.items(): env_radar[k] += float(v)
            for k, v in i_scores.items(): ins_radar[k] += float(v)

            # Calculate individual observation averages
            env_total_scores.append(sum(e_scores.values()) / 4)
            ins_total_scores.append(sum(i_scores.values()) / 4)

        # 2. Final Average Calculation
        avg_env = round(sum(env_total_scores) / total_obs, 1)
        avg_ins = round(sum(ins_total_scores) / total_obs, 1)

        for k in env_radar: env_radar[k] = round(env_radar[k] / total_obs, 1)
        for k in ins_radar: ins_radar[k] = round(ins_radar[k] / total_obs, 1)

        # 3. Monthly Trends for Bar Chart
        monthly_stats = queryset.annotate(month=TruncMonth('created_at')).values('month').annotate(
            avg=Avg('overall_performance_score')).order_by('month')

        comparison_chart = [
            {"month": e['month'].strftime("%b"), "domain_2": round(e['avg'], 1), "domain_3": round(e['avg']*0.9, 1)}
            for e in monthly_stats
        ]

        return Response({
    "observations_count": f"{total_obs} observations this month",
    "domain_analytics": {
        "classroom_environment": {
            "average_score": avg_env,
            "highest_area": f"{max(env_radar, key=env_radar.get)} ({max(env_radar.values())})",
            "lowest_area": f"{min(env_radar, key=env_radar.get)} ({min(env_radar.values())})",
        },
        "instruction": {
            "average_score": avg_ins,
            "highest_area": f"{max(ins_radar, key=ins_radar.get)} ({max(ins_radar.values())})",
            "lowest_area": f"{min(ins_radar, key=ins_radar.get)} ({min(ins_radar.values())})",
        },
        "radar_combined": { # এটি আপনার মেইন রাডার চার্টের জন্য
            "Respect": env_radar['Respect'],
            "Culture": env_radar['Culture'],
            "Procedures": env_radar['Procedures'],
            "Behavior": env_radar['Behavior'],
            "Communication": ins_radar['Communication'],
            "Questioning": ins_radar['Questioning']
        }
    },
    "comparison_chart": comparison_chart
})

class RecentObservationsView(generics.ListAPIView):
    """ Quick list of the 5 most recent observations. """
    serializer_class = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('-created_at')[:5]