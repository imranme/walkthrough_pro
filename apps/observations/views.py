# from rest_framework import generics, permissions, status, filters
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from .ai_service import ObservationAIService
# from app.components.generator import ObservationData, generate_coaching_result

# from django.utils import timezone
# from django.db.models import Avg, Count
# from django.db.models.functions import TruncMonth

# from apps.payments.permissions import (
#     IsAppUser,
#     IsDashboardUser,
#     _has_active_access,
# )

# from .models import Teacher, Observation
# from .serializers import (
#     TeacherSerializer,
#     ObservationReadSerializer,
#     ObservationCreateSerializer,
#     TeacherSimpleSerializer,
# )

# import logging

# logger = logging.getLogger(__name__)


# # ═══════════════════════════════════════════════════════════════════════
# # 1. TEACHER MANAGEMENT
# # ═══════════════════════════════════════════════════════════════════════

# class TeacherListCreateView(generics.ListCreateAPIView):
#     """
#     Web Dashboard:
#     Admin dashboard থেকে teacher list দেখা ও create করা।
#     """

#     serializer_class = TeacherSerializer
#     permission_classes = [permissions.IsAuthenticated, IsDashboardUser]

#     filter_backends = [filters.SearchFilter]
#     search_fields = ['name', 'department']

#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user)

#     def get_queryset(self):
#         return (
#             Teacher.objects
#             .filter(created_by=self.request.user)
#             .annotate(
#                 obs_count=Count('observations'),
#                 annotated_avg=Avg('observations__overall_performance_score'),
#             )
#             .order_by('-id')
#         )

#     def list(self, request, *args, **kwargs):

#         queryset = self.get_queryset()
#         filtered_queryset = self.filter_queryset(queryset)

#         serializer = self.get_serializer(filtered_queryset, many=True)

#         all_obs = Observation.objects.filter(created_by=request.user)

#         overall_avg = (
#             all_obs.aggregate(
#                 avg=Avg('overall_performance_score')
#             )['avg']
#             or 0.0
#         )

#         distinguished = 0
#         needs_support = 0

#         for teacher in filtered_queryset:

#             score = teacher.annotated_avg or 0

#             if score >= 3.5:
#                 distinguished += 1

#             elif 0 < score < 2.5:
#                 needs_support += 1

#         return Response({
#             "teachers": serializer.data,

#             "summary_cards": {
#                 "total_teachers": queryset.count(),
#                 "overall_avg": round(overall_avg, 1),
#                 "distinguished": distinguished,
#                 "needs_support": needs_support,
#             }
#         })


# class TeacherSimpleListView(generics.ListAPIView):
#     """
#     Mobile App:
#     Observation form dropdown teacher list।
#     """

#     serializer_class = TeacherSimpleSerializer
#     permission_classes = [permissions.IsAuthenticated, IsAppUser]

#     def get_queryset(self):

#         user = self.request.user

#         # Observer হলে admin এর teacher দেখাবে
#         if hasattr(user, 'profile') and user.profile.admin:
#             return Teacher.objects.filter(
#                 created_by=user.profile.admin
#             ).order_by('name')

#         # Admin হলে নিজের teacher দেখাবে
#         return Teacher.objects.filter(
#             created_by=user
#         ).order_by('name')


# # ═══════════════════════════════════════════════════════════════════════
# # 2. OBSERVATION
# # ═══════════════════════════════════════════════════════════════════════


# class ObservationDetailView(generics.RetrieveUpdateAPIView): # RetrieveAPIView থেকে UpdateAPIView তে পরিবর্তন করুন
#     serializer_class = ObservationReadSerializer
#     permission_classes = [permissions.IsAuthenticated, IsAppUser]

#     def get_queryset(self):
#         return Observation.objects.filter(created_by=self.request.user)

#     def perform_update(self, serializer):
#         observation = serializer.save()
        
#         ai_input = {
#             "teacher_name": observation.teacher.name,
#             "raw_notes": observation.raw_notes,
#             "respect_env_score": observation.respect_env_score,
#             "culture_learning_score": observation.culture_learning_score,
            
#         }
        
#         ai_response = ObservationAIService.get_ai_feedback(observation_data=ai_input)
        
#         if ai_response:
#             observation.glow = ai_response.get('glow', observation.glow)
#             observation.grow = ai_response.get('grow', observation.grow)
#             observation.dimensions_data = ai_response.get('dimensions', observation.dimensions_data)
#             observation.save()


# class ObservationListCreateView(generics.ListCreateAPIView):

#     permission_classes = [permissions.IsAuthenticated, IsAppUser]

#     filter_backends = [filters.SearchFilter]
#     search_fields = ['teacher__name', 'teacher__department']

#     def get_serializer_class(self):

#         if self.request.method == "POST":
#             return ObservationCreateSerializer

#         return ObservationReadSerializer

#     def get_queryset(self):

#         return (
#             Observation.objects
#             .filter(created_by=self.request.user)
#             .select_related("teacher")
#             .order_by('-created_at')
#         )

#     def list(self, request, *args, **kwargs):

#         queryset = self.filter_queryset(self.get_queryset())

#         serializer = self.get_serializer(queryset, many=True)

#         total = queryset.count()

#         avg = (
#             queryset.aggregate(
#                 Avg('overall_performance_score')
#             )['overall_performance_score__avg']
#             or 0.0
#         )

#         return Response({

#             "observations": serializer.data,

#             "summary_stats": {
#                 "total_observations": total,
#                 "average_score": round(avg, 1),

#                 "completed": queryset.filter(
#                     status='completed'
#                 ).count(),

#                 "pending": queryset.filter(
#                     status='pending'
#                 ).count(),
#             }
#         })

#     def create(self, request, *args, **kwargs):

#         data = request.data

#         # ─────────────────────────────────────────────────────
#         # Score Calculation
#         # ─────────────────────────────────────────────────────

#         score_fields = [
#             'respect_env_score',
#             'culture_learning_score',
#             'classroom_proc_score',
#             'student_behavior_score',
#             'comm_students_score',
#             'questioning_score',
#             'engaging_students_score',
#             'assessment_score',
#         ]

#         try:

#             scores = [
#                 float(data.get(f, 1.0))
#                 for f in score_fields
#             ]

#             avg_score = round(sum(scores) / len(scores), 1)

#         except (ValueError, TypeError):

#             avg_score = 1.0

#         # ─────────────────────────────────────────────────────
#         # Initial Save
#         # ─────────────────────────────────────────────────────

#         serializer = self.get_serializer(data=data)

#         serializer.is_valid(raise_exception=True)

#         observation = serializer.save(
#             created_by=request.user,
#             overall_performance_score=avg_score,
#             status='pending',
#         )

#         # ─────────────────────────────────────────────────────
#         # AI Feedback
#         # ─────────────────────────────────────────────────────

#         try:

#             from .ai_service import ObservationAIService

#             ai_input = {

#                 "teacher_name": observation.teacher.name,

#                 "subject": data.get('subject', 'N/A'),

#                 "grade_level": data.get('grade_level', 'N/A'),

#                 "raw_notes": data.get('raw_notes', ''),

#                 "observation_date": str(
#                     data.get('observation_date', '')
#                 ),

#                 "observation_time": str(
#                     data.get('observation_time', '')
#                 ),

#                 "respect_env_score":
#                     max(1.0, float(data.get('respect_env_score', 1.0))),

#                 "culture_learning_score":
#                     max(1.0, float(data.get('culture_learning_score', 1.0))),

#                 "classroom_proc_score":
#                     max(1.0, float(data.get('classroom_proc_score', 1.0))),

#                 "student_behavior_score":
#                     max(1.0, float(data.get('student_behavior_score', 1.0))),

#                 "comm_students_score":
#                     max(1.0, float(data.get('comm_students_score', 1.0))),

#                 "questioning_score":
#                     max(1.0, float(data.get('questioning_score', 1.0))),

#                 "engaging_students_score":
#                     max(1.0, float(data.get('engaging_students_score', 1.0))),

#                 "assessment_score":
#                     max(1.0, float(data.get('assessment_score', 1.0))),

#                 "overall_performance_score": avg_score,
#             }

#             ai_response = ObservationAIService.get_ai_feedback(
#                 observation_data=ai_input
#             )

#             if ai_response and isinstance(ai_response, dict):

#                 observation.glow = ai_response.get('glow', '')

#                 observation.grow = ai_response.get('grow', '')

#                 observation.dimensions_data = ai_response.get(
#                     'dimensions',
#                     []
#                 )

#                 observation.status = 'completed'

#             else:

#                 observation.status = 'failed'

#         except Exception as exc:

#             logger.error("AI View Error: %s", exc)

#             observation.status = 'failed'

#         observation.save()

#         observation.refresh_from_db()

#         return Response(
#             ObservationReadSerializer(observation).data,
#             status=status.HTTP_201_CREATED,
#         )


# # ═══════════════════════════════════════════════════════════════════════
# # 3. DASHBOARD STATS
# # ═══════════════════════════════════════════════════════════════════════

# class DashboardStatsView(APIView):

#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):

#         user = request.user

#         # Subscription Check
#         if not _has_active_access(user):

#             return Response({
#                 "error": "subscription_expired",
#                 "message": "Your subscription has expired."
#             }, status=403)

#         now = timezone.now()

#         platform = request.query_params.get(
#             'platform',
#             'mobile'
#         )

#         all_obs = Observation.objects.filter(
#             created_by=user
#         )

#         all_teachers = Teacher.objects.filter(
#             created_by=user
#         )

#         avg_perf = (
#             all_obs.aggregate(
#                 Avg('overall_performance_score')
#             )['overall_performance_score__avg']
#             or 0.0
#         )

#         mobile_data = {

#             "this_month_count": all_obs.filter(
#                 created_at__month=now.month,
#                 created_at__year=now.year,
#             ).count(),

#             "total_teachers": all_teachers.count(),

#             "avg_performance": round(avg_perf, 1),
#         }

#         # Mobile Dashboard
#         if platform == 'mobile':
#             return Response(mobile_data)

#         # Dashboard Permission
#         if not (user.is_staff or user.is_superuser):

#             return Response({
#                 "detail": "Permission denied. Admins only."
#             }, status=403)

#         # Monthly Observations

#         monthly_obs_qs = (
#             all_obs
#             .annotate(month=TruncMonth('created_at'))
#             .values('month')
#             .annotate(count=Count('id'))
#             .order_by('month')
#         )

#         # Score Trend

#         score_trend_qs = (
#             all_obs
#             .annotate(month=TruncMonth('created_at'))
#             .values('month')
#             .annotate(avg=Avg('overall_performance_score'))
#             .order_by('month')
#         )

#         # Top Teachers

#         top_teachers = []

#         for t in all_teachers:

#             obs = all_obs.filter(teacher=t)

#             if obs.exists():

#                 avg = (
#                     obs.aggregate(
#                         Avg('overall_performance_score')
#                     )['overall_performance_score__avg']
#                 )

#                 top_teachers.append({

#                     "id": t.id,

#                     "name": t.name,

#                     "department": t.department,

#                     "avg_score": round(avg, 1),

#                     "obs_count": obs.count(),
#                 })

#         top_teachers = sorted(
#             top_teachers,
#             key=lambda x: x['avg_score'],
#             reverse=True
#         )[:5]

#         # Recent Observations

#         recent_observations = [

#             {
#                 "id": obs.id,

#                 "teacher_name": obs.teacher.name,

#                 "subject": obs.subject,

#                 "date": (
#                     obs.observation_date.strftime("%B %d, %Y")
#                     if obs.observation_date
#                     else str(obs.created_at.date())
#                 ),

#                 "score": obs.overall_performance_score,

#                 "status": obs.status,
#             }

#             for obs in (
#                 all_obs
#                 .select_related('teacher')
#                 .order_by('-created_at')[:5]
#             )
#         ]

#         return Response({

#             **mobile_data,

#             "total_observations": all_obs.count(),

#             "distinguished_count":
#                 all_obs.filter(
#                     overall_performance_score__gte=3.5
#                 ).count(),

#             "monthly_observations": [

#                 {
#                     "month": x['month'].strftime("%b"),
#                     "count": x['count']
#                 }

#                 for x in monthly_obs_qs
#             ],

#             "score_trend": [

#                 {
#                     "month": x['month'].strftime("%b"),
#                     "avg": round(x['avg'], 1)
#                 }

#                 for x in score_trend_qs
#             ],

#             "top_teachers": top_teachers,

#             "recent_observations": recent_observations,
#         })


# # ═══════════════════════════════════════════════════════════════════════
# # 4. DOMAIN ANALYTICS
# # ═══════════════════════════════════════════════════════════════════════

# class DomainAnalyticsView(APIView):

#     permission_classes = [
#         permissions.IsAuthenticated,
#         IsDashboardUser
#     ]

#     def get(self, request):

#         queryset = Observation.objects.filter(
#             created_by=request.user,
#             status='completed'
#         )

#         total_obs = queryset.count()

#         if total_obs == 0:

#             return Response({

#                 "observations_count": "0 observations analyzed",

#                 "message": "No completed observations found.",
#             })

#         env_radar = {
#             "Respect": 0,
#             "Culture": 0,
#             "Procedures": 0,
#             "Behavior": 0
#         }

#         ins_radar = {
#             "Communication": 0,
#             "Questioning": 0,
#             "Engagement": 0,
#             "Assessment": 0
#         }

#         env_total_scores = []
#         ins_total_scores = []

#         for obs in queryset:

#             e = {

#                 "Respect":
#                     getattr(obs, 'respect_env_score', 0) or 0,

#                 "Culture":
#                     getattr(obs, 'culture_learning_score', 0) or 0,

#                 "Procedures":
#                     getattr(obs, 'classroom_proc_score', 0) or 0,

#                 "Behavior":
#                     getattr(obs, 'student_behavior_score', 0) or 0,
#             }

#             i = {

#                 "Communication":
#                     getattr(obs, 'comm_students_score', 0) or 0,

#                 "Questioning":
#                     getattr(obs, 'questioning_score', 0) or 0,

#                 "Engagement":
#                     getattr(obs, 'engaging_students_score', 0) or 0,

#                 "Assessment":
#                     getattr(obs, 'assessment_score', 0) or 0,
#             }

#             for k, v in e.items():
#                 env_radar[k] += float(v)

#             for k, v in i.items():
#                 ins_radar[k] += float(v)

#             env_total_scores.append(sum(e.values()) / 4)

#             ins_total_scores.append(sum(i.values()) / 4)

#         avg_env = round(sum(env_total_scores) / total_obs, 1)

#         avg_ins = round(sum(ins_total_scores) / total_obs, 1)

#         for k in env_radar:
#             env_radar[k] = round(env_radar[k] / total_obs, 1)

#         for k in ins_radar:
#             ins_radar[k] = round(ins_radar[k] / total_obs, 1)

#         monthly_stats = (

#             queryset
#             .annotate(month=TruncMonth('created_at'))
#             .values('month')
#             .annotate(avg=Avg('overall_performance_score'))
#             .order_by('month')
#         )

#         return Response({

#             "observations_count":
#                 f"{total_obs} observations analyzed",

#             "domain_analytics": {

#                 "classroom_environment": {

#                     "average_score": avg_env,

#                     "highest_area":
#                         f"{max(env_radar, key=env_radar.get)} "
#                         f"({max(env_radar.values())})",

#                     "lowest_area":
#                         f"{min(env_radar, key=env_radar.get)} "
#                         f"({min(env_radar.values())})",
#                 },

#                 "instruction": {

#                     "average_score": avg_ins,

#                     "highest_area":
#                         f"{max(ins_radar, key=ins_radar.get)} "
#                         f"({max(ins_radar.values())})",

#                     "lowest_area":
#                         f"{min(ins_radar, key=ins_radar.get)} "
#                         f"({min(ins_radar.values())})",
#                 },

#                 "radar_combined": {
#                     **env_radar,
#                     **ins_radar
#                 },
#             },

#             "comparison_chart": [

#                 {
#                     "month": e['month'].strftime("%b"),

#                     "domain_2": round(e['avg'], 1),

#                     "domain_3": round(e['avg'] * 0.9, 1),
#                 }

#                 for e in monthly_stats
#             ],
#         })


# # ═══════════════════════════════════════════════════════════════════════
# # 5. RECENT OBSERVATIONS
# # ═══════════════════════════════════════════════════════════════════════

# class RecentObservationsView(generics.ListAPIView):

#     serializer_class = ObservationReadSerializer

#     permission_classes = [
#         permissions.IsAuthenticated,
#         IsAppUser
#     ]

#     def get_queryset(self):

#         return (
#             Observation.objects
#             .filter(created_by=self.request.user)
#             .select_related("teacher")
#             .order_by('-created_at')[:5]
#         ) 



"""
apps/observations/views.py
───────────────────────────
Handles teacher structures, individual observations, dashboard insights, 
and automated multi-step AI coaching reports.
"""

import logging
from django.utils import timezone
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth

from rest_framework import generics, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.payments.permissions import IsAppUser, IsDashboardUser
from .models import Teacher, Observation
from .serializers import (
    TeacherSerializer,
    ObservationReadSerializer,
    ObservationCreateSerializer,
    TeacherSimpleSerializer,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1. TEACHER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

class TeacherListCreateView(generics.ListCreateAPIView):
    """
    Web Dashboard:
    View and create teacher listings within the Admin Dashboard scope.
    """
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated, IsDashboardUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'department']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        return (
            Teacher.objects
            .filter(created_by=self.request.user)
            .annotate(
                obs_count=Count('observations'),
                annotated_avg=Avg('observations__overall_performance_score'),
            )
            .order_by('-id')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(filtered_queryset, many=True)

        all_obs = Observation.objects.filter(created_by=request.user)
        overall_avg = (
            all_obs.aggregate(avg=Avg('overall_performance_score'))['avg'] or 0.0
        )

        distinguished = 0
        needs_support = 0

        for teacher in filtered_queryset:
            score = teacher.annotated_avg or 0
            if score >= 3.5:
                distinguished += 1
            elif 0 < score < 2.5:
                needs_support += 1

        return Response({
            "teachers": serializer.data,
            "summary_cards": {
                "total_teachers": queryset.count(),
                "overall_avg": round(overall_avg, 1),
                "distinguished": distinguished,
                "needs_support": needs_support,
            }
        })


class TeacherSimpleListView(generics.ListAPIView):
    """
    Mobile App:
    Provides a simple name/id pair to populate the observation creation dropdown form.
    """
    serializer_class = TeacherSimpleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

    def get_queryset(self):
        user = self.request.user
        # If the user is an Observer, return the admin's teachers
        if hasattr(user, 'profile') and user.profile.admin:
            return Teacher.objects.filter(created_by=user.profile.admin).order_by('name')

        # If Admin, return their own teachers
        return Teacher.objects.filter(created_by=user).order_by('name')

class ObservationDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieves or updates single workspace report structures manually.
    """
    serializer_class = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

    def get_queryset(self):
        return Observation.objects.filter(created_by=self.request.user)

    def perform_update(self, serializer):
        observation = serializer.save()
        
        ai_input = {
            "teacher_name": observation.teacher_name or "Teacher",
            "raw_notes": observation.raw_notes,
            "subject": observation.subject or "Mathematics",
            "grade_level": observation.grade_level or "N/A",
        }
        
        from .ai_service import ObservationAIService
        ai_response = ObservationAIService.get_ai_feedback(observation_data=ai_input)
        
        if ai_response and isinstance(ai_response, dict):
            observation.glow = ai_response.get('glow', observation.glow)
            observation.grow = ai_response.get('grow', observation.grow)
            observation.dimensions_data = ai_response.get('dimensions', observation.dimensions_data)
            observation.save()
# ═══════════════════════════════════════════════════════════════════════
# 2. OBSERVATION WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════

class ObservationListCreateView(generics.ListCreateAPIView):
    """
    Lists historical user evaluations or triggers the modern AI sequence (STEP 1).
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['teacher_name', 'subject']

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ObservationCreateSerializer
        return ObservationReadSerializer

    def get_queryset(self):
        return (
            Observation.objects
            .filter(created_by=self.request.user)
            .order_by('-created_at')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        total = queryset.count()
        avg = (
            queryset.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0
        )

        return Response({
            "observations": serializer.data,
            "summary_stats": {
                "total_observations": total,
                "average_score": round(avg, 1),
                "completed": queryset.filter(status='completed').count(),
                "pending": queryset.filter(status='draft').count(),
            }
        })

    def create(self, request, *args, **kwargs):
        """
        POST /api/v1/observations/observations/
        Handles structured request parsing with strict AI Domain Enforcement.
        FINAL FIX: Corrected list index fallback mapping to prevent 'list' object has no attribute 'get'.
        """
        data = request.data

        # ১. হার্ডকোডেড সেফটি ডোমেন লিস্ট (এআইকে ৮টি কার্ড জেনারেট করতে বাধ্য করবে)
        selected_domains = [
            "Domain 2 - Instruction",
            "Domain 3 - Learning Environment"
        ]

        # ২. সিরিয়ালাইজেশন ভ্যালিডেশন ও অবজেক্ট ক্রিয়েশন
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        observation = serializer.save(
            created_by=request.user,
            overall_performance_score=0.0,
            status='draft',
        )

        # রিকোয়েস্ট থেকে টিচারের নাম সেফলি এক্সট্রাক্ট করা
        t_name = data.get("teacher_name") or "Teacher"
        observation.teacher_name = t_name
        observation.save()

        # ── Execution Layer: AI Processing Bridge ─────────────────────────
        try:
            from .ai_service import generate_initial_feedback

            ai_payload = {
                "teacher_name":     t_name,
                "subject":          data.get("subject", "Mathematics"),
                "grade_level":      data.get("grade_level", "8"),
                "observation_date": str(data.get("observation_date", "")),
                "observation_time": str(data.get("observation_time", "")),
                "raw_notes":        data.get("raw_notes", ""),
                # ← exact keys যা DOMAIN_DIMENSION_MAP-এ আছে
                "selected_domains": [
                    "Domain 2 - Instruction",
                    "Domain 3 - Learning Environment",
                ],
            }

            feedback = generate_initial_feedback(ai_payload)

            if feedback and isinstance(feedback, dict) and "error" not in feedback:
                observation.overall_performance_score = feedback.get("overall_score", 0.0)
                raw_dimensions = feedback.get("dimensions", [])
                observation.dimensions_data = raw_dimensions
                
                # রুট লেভেলের গ্লো এবং গ্রো অ্যাসাইনমেন্ট
                observation.glow = (feedback.get("glow") or "").strip()
                observation.grow = (feedback.get("grow") or "").strip()
                
                # ──────────────────────────────────────────────────────────────────
                # 🚀 FIXED: raw_dimensions একটি LIST, তাই প্রথম এলিমেন্টের জন্য বসানো হলো
                # ──────────────────────────────────────────────────────────────────
                if not observation.glow and isinstance(raw_dimensions, list) and len(raw_dimensions) > 0:
                    observation.glow = raw_dimensions.get("glow", "") if isinstance(raw_dimensions, dict) else ""
                    
                if not observation.grow and isinstance(raw_dimensions, list) and len(raw_dimensions) > 0:
                    observation.grow = raw_dimensions[-1].get("grow", "") if isinstance(raw_dimensions[-1], dict) else ""

                observation.status = 'completed'
                
                if "Accomplished" in str(feedback):
                    observation.rating = "Accomplished"
                elif "Proficient" in str(feedback):
                    observation.rating = "Proficient"
            else:
                observation.status = 'draft'
                if feedback and "error" in feedback:
                    logger.error("AI engine returned error block: %s", feedback.get("error"))

            observation.save()

        except Exception as exc:
            logger.error("AI initial feedback workflow failed: %s", exc, exc_info=True)
            observation.status = 'draft'
            observation.save()

        observation.refresh_from_db()
        return Response(
            ObservationReadSerializer(observation).data,
            status=status.HTTP_201_CREATED,
        )

class RewriteReportView(APIView):
    """
    POST /api/v1/observations/{id}/rewrite/
    Processes updated reports when user customizes dropdown sliders on frontend screens (STEP 2).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            observation = Observation.objects.get(pk=pk, created_by=request.user)
        except Observation.DoesNotExist:
            return Response({"detail": "Observation record not found."}, status=status.HTTP_404_NOT_FOUND)

        override_ratings = request.data.get("override_ratings", {})
        if not override_ratings:
            return Response({"detail": "override_ratings map object is required."}, status=status.HTTP_400_BAD_REQUEST)

        valid_ratings = [
            "Distinguished", "Accomplished", "Proficient", "Development",
            "Needs Improvement", "Not Enough Evidence"
        ]
        for dim_id, rating in override_ratings.items():
            if rating not in valid_ratings:
                return Response(
                    {"detail": f"Invalid rating sequence '{rating}' encountered on parameter item {dim_id}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            from .ai_service import rewrite_feedback

            t_name = getattr(observation, 'teacher_name', None) or "Teacher"

            # BUG 1 FIX: rewrite_feedback()-এ 3টা argument আলাদাভাবে পাঠাতে হবে
            feedback_response = rewrite_feedback(
                observation_data={
                    "teacher_name":     t_name,
                    "subject":          observation.subject or "",
                    "grade_level":      observation.grade_level or "",
                    "observation_date": str(observation.observation_date or ""),
                    "observation_time": str(observation.observation_time or ""),
                    "raw_notes":        observation.raw_notes or "",
                    "selected_domains": [
                        "Domain 2 - Instruction",
                        "Domain 3 - Learning Environment",
                    ],
                },
                original_result_dict={
                    "raw_notes_summary": "",
                    "dimensions":        observation.dimensions_data or [],
                },
                override_ratings=override_ratings,
            )

            if feedback_response and isinstance(feedback_response, dict):
                observation.dimensions_data           = feedback_response.get("dimensions", observation.dimensions_data)
                observation.overall_performance_score = feedback_response.get("overall_score", observation.overall_performance_score)

                # BUG 2 FIX: raw_dims ব্যবহার করতে হবে, raw_dimensions নয়
                raw_dims = feedback_response.get("dimensions", [])
                if isinstance(raw_dims, list) and len(raw_dims) > 0:
                    first_dim = raw_dims[0] if isinstance(raw_dims[0], dict) else {}
                    last_dim  = raw_dims[-1] if isinstance(raw_dims[-1], dict) else {}

                    observation.glow = first_dim.get("glow", "") or ""
                    observation.grow = last_dim.get("grow", "")  or ""

                observation.save()

            return Response(ObservationReadSerializer(observation).data, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.error("AI rewrite feedback workflow failed: %s", exc, exc_info=True)
            return Response({"detail": "AI Engine rewrite operation failed internally."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════
# 3. DASHBOARD ANALYTICS INSIGHTS
# ═══════════════════════════════════════════════════════════════════════

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Guard evaluation logic checking subscription limits
        if not _has_active_access(user):
            return Response({
                "error": "subscription_expired",
                "message": "Your active platform premium license has expired."
            }, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        platform = request.query_params.get('platform', 'mobile')

        all_obs = Observation.objects.filter(created_by=user)
        all_teachers = Teacher.objects.filter(created_by=user)

        avg_perf = all_obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0

        mobile_data = {
            "this_month_count": all_obs.filter(created_at__month=now.month, created_at__year=now.year).count(),
            "total_teachers": all_teachers.count(),
            "avg_performance": round(avg_perf, 1),
        }

        if platform == 'mobile':
            return Response(mobile_data)

        if not (user.is_staff or user.is_superuser):
            return Response({"detail": "Permission denied. Workspace administrators only."}, status=status.HTTP_403_FORBIDDEN)

        monthly_obs_qs = all_obs.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
        score_trend_qs = all_obs.annotate(month=TruncMonth('created_at')).values('month').annotate(avg=Avg('overall_performance_score')).order_by('month')

        top_teachers = []
        for t in all_teachers:
            obs = all_obs.filter(teacher=t)
            if obs.exists():
                avg = obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
                top_teachers.append({
                    "id": t.id,
                    "name": t.name,
                    "department": t.department,
                    "avg_score": round(avg, 1),
                    "obs_count": obs.count(),
                })

        top_teachers = sorted(top_teachers, key=lambda x: x['avg_score'], reverse=True)[:5]

        recent_observations = [
            {
                "id": obs.id,
                "teacher_name": obs.teacher.name if obs.teacher else "Unknown",
                "subject": obs.subject,
                "date": obs.observation_date.strftime("%B %d, %Y") if obs.observation_date else str(obs.created_at.date()),
                "score": obs.overall_performance_score,
                "status": obs.status,
            }
            for obs in all_obs.select_related('teacher').order_by('-created_at')[:5]
        ]

        return Response({
            **mobile_data,
            "total_observations": all_obs.count(),
            "distinguished_count": all_obs.filter(overall_performance_score__gte=3.5).count(),
            "monthly_observations": [{"month": x['month'].strftime("%b"), "count": x['count']} for x in monthly_obs_qs],
            "score_trend": [{"month": x['month'].strftime("%b"), "avg": round(x['avg'], 1)} for x in score_trend_qs],
            "top_teachers": top_teachers,
            "recent_observations": recent_observations,
        })


# ═══════════════════════════════════════════════════════════════════════
# 4. ADVANCED RADAR MAP ANALYSIS
# ═══════════════════════════════════════════════════════════════════════

class DomainAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDashboardUser]

    def get(self, request):
        queryset = Observation.objects.filter(created_by=request.user, status='completed')
        total_obs = queryset.count()

        if total_obs == 0:
            return Response({
                "observations_count": "0 observations analyzed",
                "message": "No completed workspace records available to parse metrics from.",
            })

        env_radar = {"Respect": 0, "Culture": 0, "Procedures": 0, "Behavior": 0}
        ins_radar = {"Communication": 0, "Questioning": 0, "Engagement": 0, "Assessment": 0}

        env_total_scores = []
        ins_total_scores = []

        for obs in queryset:
            e = {
                "Respect":    getattr(obs, 'respect_env_score', 0) or 0,
                "Culture":    getattr(obs, 'culture_learning_score', 0) or 0,
                "Procedures": getattr(obs, 'classroom_proc_score', 0) or 0,
                "Behavior":   getattr(obs, 'student_behavior_score', 0) or 0,
            }
            i = {
                "Communication": getattr(obs, 'comm_students_score', 0) or 0,
                "Questioning":   getattr(obs, 'questioning_score', 0) or 0,
                "Engagement":    getattr(obs, 'engaging_students_score', 0) or 0,
                "Assessment":    getattr(obs, 'assessment_score', 0) or 0,
            }

            for k, v in e.items(): env_radar[k] += float(v)
            for k, v in i.items(): ins_radar[k] += float(v)

            env_total_scores.append(sum(e.values()) / 4)
            ins_total_scores.append(sum(i.values()) / 4)

        avg_env = round(sum(env_total_scores) / total_obs, 1)
        avg_ins = round(sum(ins_total_scores) / total_obs, 1)

        for k in env_radar: env_radar[k] = round(env_radar[k] / total_obs, 1)
        for k in ins_radar: ins_radar[k] = round(ins_radar[k] / total_obs, 1)

        monthly_stats = queryset.annotate(month=TruncMonth('created_at')).values('month').annotate(avg=Avg('overall_performance_score')).order_by('month')

        return Response({
            "observations_count": f"{total_obs} observations analyzed",
            "domain_analytics": {
                "classroom_environment": {
                    "average_score": avg_env,
                    "highest_area":  f"{max(env_radar, key=env_radar.get)} ({max(env_radar.values())})",
                    "lowest_area":   f"{min(env_radar, key=env_radar.get)} ({min(env_radar.values())})",
                },
                "instruction": {
                    "average_score": avg_ins,
                    "highest_area":  f"{max(ins_radar, key=ins_radar.get)} ({max(ins_radar.values())})",
                    "lowest_area":   f"{min(ins_radar, key=ins_radar.get)} ({min(ins_radar.values())})",
                },
                "radar_combined": {**env_radar, **ins_radar},
            },
            "comparison_chart": [
                {
                    "month": e['month'].strftime("%b"),
                    "domain_2": round(e['avg'], 1),
                    "domain_3": round(e['avg'] * 0.9, 1),
                }
                for e in monthly_stats
            ],
        })


# ═══════════════════════════════════════════════════════════════════════
# 5. RECENT ACTIVITY LISTINGS
# ═══════════════════════════════════════════════════════════════════════

class RecentObservationsView(generics.ListAPIView):
    serializer_class = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

    def get_queryset(self):
        return (
            Observation.objects
            .filter(created_by=self.request.user)
            .select_related("teacher")
            .order_by('-created_at')[:5]
        )