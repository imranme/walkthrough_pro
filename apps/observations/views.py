import logging
from django.utils import timezone
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
from rest_framework.permissions import IsAuthenticated

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
        return Teacher.objects.filter(created_by=self.request.user).order_by('-id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        all_obs = Observation.objects.filter(created_by=request.user)
        
        for teacher in queryset:
            teacher.observations = all_obs.filter(teacher_name=teacher.name)

        serializer = self.get_serializer(queryset, many=True)
        teachers_data = serializer.data

        overall_avg = (
            all_obs.aggregate(avg=Avg('overall_performance_score'))['avg'] or 0.0
        )

        distinguished = 0
        needs_support = 0

        for t_data in teachers_data:
            t_obs = all_obs.filter(teacher_name=t_data['name'])
            t_avg = t_obs.aggregate(avg=Avg('overall_performance_score'))['avg'] or 0.0
            
            t_data['obs_count'] = t_obs.count()
            t_data['annotated_avg'] = round(t_avg, 1)

            if t_avg >= 3.5:
                distinguished += 1
            elif 0 < t_avg < 2.5:
                needs_support += 1

        return Response({
            "teachers": teachers_data,
            "summary_cards": {
                "total_teachers": queryset.count(),
                "overall_avg": round(overall_avg, 1),
                "distinguished": distinguished,
                "needs_support": needs_support,
            }
        })


# ═══════════════════════════════════════════════════════════════════════
# 2. OBSERVATION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

class ObservationListCreateView(generics.ListCreateAPIView):
    """
    Lists historical user evaluations or triggers the modern AI sequence (STEP 1).
    """
    
    permission_classes = [permissions.IsAuthenticated, IsAppUser]
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
            queryset.aggregate(avg_score=Avg('overall_performance_score'))['avg_score'] or 0.0
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
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        observation = serializer.save(
            created_by=request.user,
            overall_performance_score=0.0,
            status='draft',
        )

        t_name = data.get("teacher_name") or "Teacher"
        observation.teacher_name = t_name
        observation.save()

        try:
            from .ai_service import generate_initial_feedback

            ai_payload = {
                "teacher_name":     t_name,
                "subject":          data.get("subject", "Mathematics"),
                "grade_level":      data.get("grade_level", "8"),
                "observation_date": str(data.get("observation_date", "")),
                "observation_time": str(data.get("observation_time", "")),
                "raw_notes":        data.get("raw_notes", ""),
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
                
                observation.glow = (feedback.get("glow") or "").strip()
                observation.grow = (feedback.get("grow") or "").strip()
                
                if isinstance(raw_dimensions, list) and len(raw_dimensions) > 0:
                    first_dim = raw_dimensions
                    last_dim = raw_dimensions[-1]
                    
                    if not observation.glow and isinstance(first_dim, dict):
                        observation.glow = first_dim.get("glow", "")
                        
                    if not observation.grow and isinstance(last_dim, dict):
                        observation.grow = last_dim.get("grow", "")

                observation.status = 'completed'
                
                if "Accomplished" in str(feedback):
                    observation.rating = "Accomplished"
                elif "Proficient" in str(feedback):
                    observation.rating = "Proficient"
            else:
                observation.status = 'draft'

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


class TeacherSimpleListView(generics.ListAPIView):
    """
    Mobile App & Observation Page Dropdowns:
    Provides a simple name/id pair to populate the observation creation dropdown form.
    """
    serializer_class = TeacherSimpleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.admin:
            return Teacher.objects.filter(created_by=user.profile.admin).order_by('name')

        return Teacher.objects.filter(created_by=user).order_by('name')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        all_obs = Observation.objects.filter(created_by=request.user)
        
        for teacher in queryset:
            teacher.observations = all_obs.filter(teacher_name=teacher.name)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ObservationDetailView(APIView):
    """
    Handles GET, PUT, and DELETE requests cleanly for a single observation instance,
    bypassing generic serializer/filter layer field resolution errors.
    """
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

    def get(self, request, pk):
        try:
            observation = Observation.objects.get(pk=pk, created_by=request.user)
            serializer = ObservationReadSerializer(observation)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Observation.DoesNotExist:
            return Response({"error": "Observation not found or permission denied."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk):
        try:
            observation = Observation.objects.get(pk=pk, created_by=request.user)
            serializer = ObservationReadSerializer(observation, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_obs = serializer.save()

            ai_input = {
                "teacher_name": updated_obs.teacher_name or "Teacher",
                "raw_notes": updated_obs.raw_notes,
                "subject": updated_obs.subject or "Mathematics",
                "grade_level": updated_obs.grade_level or "N/A",
            }
            
            from .ai_service import ObservationAIService
            ai_response = ObservationAIService.get_ai_feedback(observation_data=ai_input)
            
            if ai_response and isinstance(ai_response, dict):
                updated_obs.glow = ai_response.get('glow', updated_obs.glow)
                updated_obs.grow = ai_response.get('grow', updated_obs.grow)
                updated_obs.dimensions_data = ai_response.get('dimensions', updated_obs.dimensions_data)
                updated_obs.save()

            return Response(ObservationReadSerializer(updated_obs).data, status=status.HTTP_200_OK)
        except Observation.DoesNotExist:
            return Response({"error": "Observation not found or permission denied."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            # Direct QuerySet deletion forces immediate SQL cleanup without hitting internal model/signal mappings
            deleted_count, _ = Observation.objects.filter(pk=pk, created_by=request.user).delete()
            
            if deleted_count == 0:
                return Response(
                    {"error": "Observation not found or permission denied."}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
            return Response(
                {"message": "Observation deleted successfully."}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RewriteReportView(APIView):
    """
    POST /api/v1/observations/{id}/rewrite/
    Processes updated reports when user customizes dropdown sliders on frontend screens (STEP 2).
    """
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

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

                raw_dims = feedback_response.get("dimensions", [])
                if isinstance(raw_dims, list) and len(raw_dims) > 0:
                    first_dim = raw_dims if isinstance(raw_dims, dict) else {}
                    last_dim  = raw_dims[-1] if isinstance(raw_dims[-1], dict) else {}

                    observation.glow = first_dim.get("glow", "") or ""
                    observation.grow = last_dim.get("grow", "")  or ""

                observation.save()

            return Response(ObservationReadSerializer(observation).data, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.error("AI rewrite feedback workflow failed: %s", exc, exc_info=True)
            return Response({"detail": "AI Engine rewrite operation failed internally."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════
# 3. DASHBOARD STATS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAppUser]

    def get(self, request):
        user = request.user
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

        # মোবাইল রিকোয়েস্টের জন্য ডেটা রিটার্ন করা হলো
        if platform == 'mobile':
            return Response(mobile_data)

        # 🔒 ওয়েব প্ল্যাটফর্মের ক্ষেত্রে কঠোর সিকিউরিটি লকিং মেকানিজম
        # ট্রায়াল শেষ হলে বা অবজারভার ড্যাশবোর্ড দেখতে চাইলে IsDashboardUser এর ম্যানুয়াল ভ্যালিডেশন ট্রিগার
        from rest_framework.exceptions import PermissionDenied
        from apps.payments.permissions import IsDashboardUser, WEB_TRIAL_EXPIRED_RESPONSE, DASHBOARD_FORBIDDEN
        
        # সুপার অ্যাডমিন ছাড়া বাকিদের জন্য রোল এবং ট্রায়াল স্ট্যাটাস চেক
        if not (user.is_staff or user.is_superuser):
            # ১. রিকোয়েস্টকারী অবজারভার হলে আজীবন ব্লক
            if hasattr(user, 'profile') and getattr(user.profile, 'is_observer', False):
                raise PermissionDenied(detail=DASHBOARD_FORBIDDEN)
            
            # ২. ট্রায়াল পিরিয়ড ওভার হয়ে গেলে ড্যাশবোর্ড লক স্ক্রিন পুশ
            try:
                sub = user.subscription
                if not sub.has_app_access:
                    raise PermissionDenied(detail=WEB_TRIAL_EXPIRED_RESPONSE)
            except Exception:
                raise PermissionDenied(detail={"error": "no_subscription", "message": "No subscription found."})

        # ড্যাশবোর্ড পারমিশন গ্র্যান্টেড হলে ডাটাবেজ প্রসেসিং ফ্লো
        monthly_obs_qs = all_obs.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
        score_trend_qs = all_obs.annotate(month=TruncMonth('created_at')).values('month').annotate(avg=Avg('overall_performance_score')).order_by('month')

        top_teachers = []
        for t in all_teachers:
            obs = all_obs.filter(teacher_name=t.name)
            if obs.exists():
                avg = obs.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg'] or 0.0
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
                "teacher_name": getattr(obs, 'teacher_name', 'Unknown') or "Unknown",
                "subject": obs.subject,
                "date": obs.observation_date.strftime("%B %d, %Y") if obs.observation_date else str(obs.created_at.date()),
                "score": obs.overall_performance_score,
                "status": obs.status,
            }
            for obs in all_obs.order_by('-created_at')[:5]
        ]

        return Response({
            **mobile_data,
            "total_observations": all_obs.count(),
            "distinguished_count": all_obs.filter(overall_performance_score__gte=3.5).count(),
            "monthly_observations": [{"month": x['month'].strftime("%b") if x['month'] else "N/A", "count": x['count']} for x in monthly_obs_qs],
            "score_trend": [{"month": x['month'].strftime("%b") if x['month'] else "N/A", "avg": round(x['avg'], 1)} for x in score_trend_qs],
            "top_teachers": top_teachers,
            "recent_observations": recent_observations,
        })


class DomainAnalyticsView(APIView):
    """
    Advanced radar map analytics data provider for workspace managers.
    """
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
                    "month": e['month'].strftime("%b") if e['month'] else "N/A",
                    "domain_2": round(e['avg'], 1),
                    "domain_3": round(e['avg'] * 0.9, 1),
                }
                for e in monthly_stats
            ],
        })


# ═══════════════════════════════════════════════════════════════════════
# 4. RECENT ACTIVITY LISTINGS
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

