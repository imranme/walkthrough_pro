
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
    ObservationCreateSerializer,
    TeacherSimpleSerializer,
)
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1. TEACHER
# ═══════════════════════════════════════════════════════════════════════

class TeacherListCreateView(generics.ListCreateAPIView):
    serializer_class   = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['name', 'department']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        # FIX: annotate name "annotated_avg" — model-এর @property avg_score এর সাথে conflict নেই
        return Teacher.objects.filter(created_by=self.request.user).annotate(
            obs_count=Count('observations'),
            annotated_avg=Avg('observations__overall_performance_score'),
        ).order_by('-id')

    def list(self, request, *args, **kwargs):
        queryset          = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)
        serializer        = self.get_serializer(filtered_queryset, many=True)

        all_obs     = Observation.objects.filter(created_by=request.user)
        overall_avg = all_obs.aggregate(
            avg=Avg('overall_performance_score')
        )['avg'] or 0.0

        distinguished = 0
        needs_support = 0
        for teacher in filtered_queryset:
            # FIX: annotated_avg ব্যবহার করুন
            score = teacher.annotated_avg or 0
            if score >= 3.5:
                distinguished += 1
            elif 0 < score < 2.5:
                needs_support += 1

        return Response({
            "teachers": serializer.data,
            "summary_cards": {
                "total_teachers": queryset.count(),
                "overall_avg":    round(overall_avg, 1),
                "distinguished":  distinguished,
                "needs_support":  needs_support,
            }
        })


class TeacherSimpleListView(generics.ListAPIView):
    """Mobile Observation Form-এর Select Teacher dropdown।"""
    serializer_class   = TeacherSimpleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Teacher.objects.filter(
            created_by=self.request.user
        ).order_by('name')


# ═══════════════════════════════════════════════════════════════════════
# 2. OBSERVATION
# ═══════════════════════════════════════════════════════════════════════

class ObservationDetailView(generics.RetrieveAPIView):
    serializer_class   = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Observation.objects.filter(created_by=self.request.user)


class ObservationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['teacher__name', 'teacher__department']

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ObservationCreateSerializer
        return ObservationReadSerializer

    def get_queryset(self):
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset   = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        total = queryset.count()
        avg   = queryset.aggregate(
            Avg('overall_performance_score')
        )['overall_performance_score__avg'] or 0.0

        return Response({
            "observations": serializer.data,
            "summary_stats": {
                "total_observations": total,
                "average_score":      round(avg, 1),
                "completed":          queryset.filter(status='completed').count(),
                "pending":            queryset.filter(status='pending').count(),
            }
        })

    def create(self, request, *args, **kwargs):
        data = request.data

        # ── Score calculation ──────────────────────────────────────────
        score_fields = [
            'respect_env_score', 'culture_learning_score', 'classroom_proc_score',
            'student_behavior_score', 'comm_students_score', 'questioning_score',
            'engaging_students_score', 'assessment_score',
        ]
        try:
            scores    = [float(data.get(f, 1.0)) for f in score_fields]
            avg_score = round(sum(scores) / len(scores), 1)
        except (ValueError, TypeError):
            avg_score = 1.0

        # ── Initial save ───────────────────────────────────────────────
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        observation = serializer.save(
            created_by              = request.user,
            overall_performance_score = avg_score,
            status                  = 'pending',
        )

        # ── AI call ────────────────────────────────────────────────────
        try:
            from .ai_service import ObservationAIService

            ai_input = {
                "teacher_name":    observation.teacher.name,
                "subject":         data.get('subject', 'N/A'),
                "grade_level":     data.get('grade_level', 'N/A'),
                "raw_notes":       data.get('raw_notes', ''),
                "observation_date": str(data.get('observation_date', '')),
                "observation_time": str(data.get('observation_time', '')),
                # FIX: exact key names → ai_service.py এর mapping-এর সাথে মেলে
                "respect_env_score":       max(1.0, float(data.get('respect_env_score',       1.0))),
                "culture_learning_score":  max(1.0, float(data.get('culture_learning_score',  1.0))),
                "classroom_proc_score":    max(1.0, float(data.get('classroom_proc_score',    1.0))),
                "student_behavior_score":  max(1.0, float(data.get('student_behavior_score',  1.0))),
                "comm_students_score":     max(1.0, float(data.get('comm_students_score',     1.0))),
                "questioning_score":       max(1.0, float(data.get('questioning_score',       1.0))),
                "engaging_students_score": max(1.0, float(data.get('engaging_students_score', 1.0))),
                "assessment_score":        max(1.0, float(data.get('assessment_score',        1.0))),
                "overall_performance_score": avg_score,
            }

            ai_response = ObservationAIService.get_ai_feedback(observation_data=ai_input)

            if ai_response and isinstance(ai_response, dict):
                observation.glow           = ai_response.get('glow', '')
                observation.grow           = ai_response.get('grow', '')
                observation.dimensions_data = ai_response.get('dimensions', [])
                observation.status         = 'completed'
            else:
                observation.status = 'failed'

        except Exception as exc:
            logger.error("AI View Error: %s", exc)
            observation.status = 'failed'

        observation.save()
        observation.refresh_from_db()

        return Response(
            ObservationReadSerializer(observation).data,
            status=status.HTTP_201_CREATED,
        )


# ═══════════════════════════════════════════════════════════════════════
# 3. DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user     = request.user
        now      = timezone.now()
        platform = request.query_params.get('platform', 'mobile')

        all_obs      = Observation.objects.filter(created_by=user)
        all_teachers = Teacher.objects.filter(created_by=user)

        avg_perf = all_obs.aggregate(
            Avg('overall_performance_score')
        )['overall_performance_score__avg'] or 0.0

        mobile_data = {
            "this_month_count": all_obs.filter(
                created_at__month=now.month,
                created_at__year=now.year,
            ).count(),
            "total_teachers":  all_teachers.count(),
            "avg_performance": round(avg_perf, 1),
        }

        if platform == 'mobile':
            return Response(mobile_data)

        # Web dashboard — is_staff check
        if not (user.is_staff or user.is_superuser):
            return Response(
                {"detail": "Permission denied. Admins only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Bar chart
        monthly_obs_qs = (
            all_obs.annotate(month=TruncMonth('created_at'))
            .values('month').annotate(count=Count('id'))
            .order_by('month')
        )

        # Line chart
        score_trend_qs = (
            all_obs.annotate(month=TruncMonth('created_at'))
            .values('month').annotate(avg=Avg('overall_performance_score'))
            .order_by('month')
        )

        # Top teachers
        top_teachers = []
        for t in all_teachers:
            obs = all_obs.filter(teacher=t)
            if obs.exists():
                avg = obs.aggregate(
                    Avg('overall_performance_score')
                )['overall_performance_score__avg']
                top_teachers.append({
                    "id":        t.id,
                    "name":      t.name,
                    "department": t.department,
                    "avg_score": round(avg, 1),
                    "obs_count": obs.count(),
                })
        top_teachers = sorted(
            top_teachers, key=lambda x: x['avg_score'], reverse=True
        )[:5]

        # Recent observations
        recent_observations = [
            {
                "id":           obs.id,
                "teacher_name": obs.teacher.name,
                "subject":      obs.subject,
                "date": (
                    obs.observation_date.strftime("%B %d, %Y")
                    if obs.observation_date
                    else str(obs.created_at.date())
                ),
                "score":  obs.overall_performance_score,
                "status": obs.status,
            }
            for obs in all_obs.select_related('teacher').order_by('-created_at')[:5]
        ]

        return Response({
            **mobile_data,
            "total_observations":  all_obs.count(),
            "distinguished_count": all_obs.filter(overall_performance_score__gte=3.5).count(),
            "monthly_observations": [
                {"month": x['month'].strftime("%b"), "count": x['count']}
                for x in monthly_obs_qs
            ],
            "score_trend": [
                {"month": x['month'].strftime("%b"), "avg": round(x['avg'], 1)}
                for x in score_trend_qs
            ],
            "top_teachers":        top_teachers,
            "recent_observations": recent_observations,
        })


# ═══════════════════════════════════════════════════════════════════════
# 4. DOMAIN ANALYTICS
# FIX: IsAdminUser সরিয়ে IsAuthenticated রাখা হয়েছে — 502 fix
# ═══════════════════════════════════════════════════════════════════════

class DomainAnalyticsView(APIView):
    # FIX: IsAdminUser ছিল → 502 দিচ্ছিল। এখন সব authenticated user দেখতে পারবে
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset  = Observation.objects.filter(
            created_by=request.user, status='completed'
        )
        total_obs = queryset.count()

        if total_obs == 0:
            return Response({
                "observations_count": "0 observations analyzed",
                "message": "No completed observations found.",
            })

        env_radar = {"Respect": 0, "Culture": 0, "Procedures": 0, "Behavior": 0}
        ins_radar = {"Communication": 0, "Questioning": 0, "Engagement": 0, "Assessment": 0}
        env_total_scores = []
        ins_total_scores = []

        for obs in queryset:
            e = {
                "Respect":    getattr(obs, 'respect_env_score',       0) or 0,
                "Culture":    getattr(obs, 'culture_learning_score',  0) or 0,
                "Procedures": getattr(obs, 'classroom_proc_score',    0) or 0,
                "Behavior":   getattr(obs, 'student_behavior_score',  0) or 0,
            }
            i = {
                "Communication": getattr(obs, 'comm_students_score',     0) or 0,
                "Questioning":   getattr(obs, 'questioning_score',       0) or 0,
                "Engagement":    getattr(obs, 'engaging_students_score', 0) or 0,
                "Assessment":    getattr(obs, 'assessment_score',        0) or 0,
            }
            for k, v in e.items(): env_radar[k] += float(v)
            for k, v in i.items(): ins_radar[k] += float(v)
            env_total_scores.append(sum(e.values()) / 4)
            ins_total_scores.append(sum(i.values()) / 4)

        avg_env = round(sum(env_total_scores) / total_obs, 1)
        avg_ins = round(sum(ins_total_scores) / total_obs, 1)
        for k in env_radar: env_radar[k] = round(env_radar[k] / total_obs, 1)
        for k in ins_radar: ins_radar[k] = round(ins_radar[k] / total_obs, 1)

        monthly_stats = (
            queryset.annotate(month=TruncMonth('created_at'))
            .values('month').annotate(avg=Avg('overall_performance_score'))
            .order_by('month')
        )

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
                    "month":    e['month'].strftime("%b"),
                    "domain_2": round(e['avg'], 1),
                    "domain_3": round(e['avg'] * 0.9, 1),
                }
                for e in monthly_stats
            ],
        })


# ═══════════════════════════════════════════════════════════════════════
# 5. RECENT OBSERVATIONS
# ═══════════════════════════════════════════════════════════════════════

class RecentObservationsView(generics.ListAPIView):
    serializer_class   = ObservationReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Observation.objects.filter(
            created_by=self.request.user
        ).select_related("teacher").order_by('-created_at')[:5]
