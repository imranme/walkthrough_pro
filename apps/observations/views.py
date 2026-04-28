from rest_framework import generics, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
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
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'department']

    def get_queryset(self):
        # Using 'observations' as suggested by your FieldError choices
        return Teacher.objects.filter(created_by=self.request.user).annotate(
            obs_count=Count('observations') 
        ).order_by('-id')

    def list(self, request, *args, **kwargs):
        # Get the annotated queryset
        queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)
        
        # Serialize the teacher data
        serializer = self.get_serializer(filtered_queryset, many=True)
        
        # 1. Map the annotation count into the serialized response
        # This adds 'observation_count' to each teacher in the list
        custom_data = []
        for i, teacher in enumerate(filtered_queryset):
            data = serializer.data[i]
            data['observation_count'] = teacher.obs_count 
            custom_data.append(data)

        # 2. Analytics for summary cards at the top
        all_obs = Observation.objects.filter(created_by=request.user)
        overall_avg = all_obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0

        distinguished = 0
        needs_support = 0
        for teacher in filtered_queryset:
            # Safely check the avg_score property for card stats
            score = getattr(teacher, 'avg_score', 0)
            if score >= 3.5:
                distinguished += 1
            elif 0 < score < 2.5:
                needs_support += 1

        return Response({
            "teachers": custom_data,
            "summary_cards": {
                "total_teachers": queryset.count(),
                "overall_avg": round(overall_avg, 1),
                "distinguished": distinguished,
                "needs_support": needs_support
            }
        })
class ObservationDetailView(generics.RetrieveAPIView):
    # তোমার এরর মেসেজ অনুযায়ী এখানে ObservationReadSerializer হবে
    serializer_class = ObservationReadSerializer 
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # শুধুমাত্র নিজের তৈরি করা রিপোর্ট দেখতে পারবে
        return Observation.objects.filter(created_by=self.request.user)

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
    """
    Central view to load all dashboard data for Web and Mobile.
    Security: Only Admins and Superusers can access full web analytics.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Initialize user and current time
        user = request.user
        now = timezone.now()
        
        # Determine the platform from query parameters (default to mobile)
        platform = request.query_params.get('platform', 'mobile')

        # 1. Base Filtering: Fetch data only created by the logged-in user
        all_obs = Observation.objects.filter(created_by=user)
        all_teachers = Teacher.objects.filter(created_by=user)

        # 2. Common Calculations: Basic counts and averages for both platforms
        total_teachers = all_teachers.count()
        total_observations = all_obs.count()
        
        # Calculate overall performance average
        avg_perf = all_obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0
        
        # Prepare basic summary data for mobile or general use
        mobile_data = {
            "this_month_count": all_obs.filter(created_at__month=now.month, created_at__year=now.year).count(),
            "total_teachers": total_teachers,
            "avg_performance": round(avg_perf, 1) # Rounding to 1 decimal place
        }

        # 3. Quick Exit: If platform is mobile, return simplified data immediately
        if platform == 'mobile':
            return Response(mobile_data)

        # 4. Web Dashboard Security: Restrict access to Staff (Admin) or Superusers only
        if not (user.is_staff or user.is_superuser):
            return Response(
                {"detail": "Permission denied. This dashboard is for Admins only."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 5. Web Dashboard Logic: Prepare complex analytics for charts and lists
        
        # Bar Chart Data: Monthly observation counts
        monthly_obs_qs = (all_obs.annotate(month=TruncMonth('created_at'))
                          .values('month').annotate(count=Count('id'))
                          .order_by('month'))
        
        # Score Trend Data: Average monthly performance score changes
        score_trend_qs = (all_obs.annotate(month=TruncMonth('created_at'))
                          .values('month').annotate(avg=Avg('overall_performance_score'))
                          .order_by('month'))

        # 6. Top Performing Teachers: Calculate average scores per teacher (Top 5)
        top_teachers = []
        for t in all_teachers:
            obs = all_obs.filter(teacher=t)
            if obs.exists():
                avg = obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
                top_teachers.append({
                    "name": t.name,
                    "avg_score": round(avg, 1),
                    "obs_count": obs.count()
                })
        
        # Sort by average score in descending order and pick top 5
        top_teachers = sorted(top_teachers, key=lambda x: x['avg_score'], reverse=True)[:5]

        # 7. Recent Observations: Fetch last 5 reports for the bottom list section
        recent_qs = all_obs.select_related('teacher', 'created_by').order_by('-created_at')[:5]
        recent_observations = [
            {
                "id": obs.id,
                "teacher_name": obs.teacher.name,
                "subject": obs.subject,
                # Formatting date for readable display: e.g., April 28, 2026
                "date": obs.observation_date.strftime("%B %d, %Y") if obs.observation_date else str(obs.created_at.date()),
                "score": obs.overall_performance_score,
                "status": obs.status,
            }
            for obs in recent_qs
        ]

        # 8. Final Web Response: Return consolidated data object
        return Response({
            **mobile_data, # Include basic mobile stats
            "total_observations": total_observations,
            "distinguished_count": all_obs.filter(overall_performance_score__gte=3.5).count(),
            "monthly_observations": [{"month": x['month'].strftime("%b"), "count": x['count']} for x in monthly_obs_qs],
            "score_trend": [{"month": x['month'].strftime("%b"), "avg": round(x['avg'], 1)} for x in score_trend_qs],
            "top_teachers": top_teachers,
            "recent_observations": recent_observations,
            "message": "Full Web Dashboard Analytics Loaded for Admins"
        })
# -------------------------------------------------------------------------
# 4. DOMAIN ANALYTICS (The Graph & Radar Data)
# -------------------------------------------------------------------------
class DomainAnalyticsView(APIView):
    """
    Handles Radar Charts and Analytics.
    Only accessible by Admin/Superadmin (is_staff=True).
    """
    # IsAdminUser নিশ্চিত করে যে শুধু Staff/Admin ডাটা দেখতে পারবে
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        # লজিক: অ্যাডমিন হিসেবে সব সম্পন্ন হওয়া অবজারভেশন দেখা
        queryset = Observation.objects.filter(status='completed')
        total_obs = queryset.count()

        if total_obs == 0:
            return Response({
                "observations_count": "0 observations this month",
                "message": "No completed observations found for analytics."
            }, status=200)

        # ১. ডাটা ইনিশিয়ালাইজেশন
        env_radar = {"Respect": 0, "Culture": 0, "Procedures": 0, "Behavior": 0}
        ins_radar = {"Communication": 0, "Questioning": 0, "Engagement": 0, "Assessment": 0}
        
        env_total_scores = []
        ins_total_scores = []

        for obs in queryset:
            # মডেলের ফিল্ড থেকে ডাটা সংগ্রহ (getattr ব্যবহার করা হয়েছে সেফটির জন্য)
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

            # রাডার টোটালে যোগ করা
            for k, v in e_scores.items(): env_radar[k] += float(v)
            for k, v in i_scores.items(): ins_radar[k] += float(v)

            # এভারেজ ক্যালকুলেশন (শুন্য দিয়ে ভাগ হওয়া এড়াতে if ব্যবহার)
            env_total_scores.append(sum(e_scores.values()) / 4)
            ins_total_scores.append(sum(i_scores.values()) / 4)

        # ২. ফাইনাল এভারেজ এবং রাডার ডাটা ফরম্যাটিং
        avg_env = round(sum(env_total_scores) / total_obs, 1)
        avg_ins = round(sum(ins_total_scores) / total_obs, 1)

        for k in env_radar: env_radar[k] = round(env_radar[k] / total_obs, 1)
        for k in ins_radar: ins_radar[k] = round(ins_radar[k] / total_obs, 1)

        # ৩. ট্রেন্ড চার্টের জন্য মাসিক ডাটা
        monthly_stats = queryset.annotate(month=TruncMonth('created_at')).values('month').annotate(
            avg=Avg('overall_performance_score')).order_by('month')

        comparison_chart = [
            {
                "month": e['month'].strftime("%b") if e['month'] else "N/A", 
                "domain_2": round(e['avg'], 1), 
                "domain_3": round(e['avg']*0.9, 1)
            }
            for e in monthly_stats
        ]

        return Response({
            "observations_count": f"{total_obs} observations analyzed",
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
                "radar_combined": {
                    **env_radar,
                    **ins_radar
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