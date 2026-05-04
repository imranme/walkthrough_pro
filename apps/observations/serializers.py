from rest_framework import serializers
from .models import Teacher, Observation
from django.db.models import Avg
from django.db.models.functions import TruncMonth
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated


class TeacherSerializer(serializers.ModelSerializer):
    # Annotate kora field gulo ke read_only hisebe define korun
    avg_score = serializers.FloatField(read_only=True)
    observations_count = serializers.IntegerField(source='obs_count', read_only=True)
    last_observation = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        # 'created_by' field ti list e dorkar na holeo model e thakte hobe 
        # kintu seta read_only hobe
        fields = ['id', 'name', 'department', 'avg_score', 'observations_count', 'last_observation']
        read_only_fields = ['created_by']

    def get_last_observation(self, obj):
        # 'observations' as the related name from your FieldError context
        last_obs = obj.observations.order_by('-observation_date').first()
        if last_obs and last_obs.observation_date:
            return last_obs.observation_date.strftime("%B %d, %Y")
        return "No data"

class ObservationReadSerializer(serializers.ModelSerializer):
    """
    Detailed view of an Observation for the UI.
    Maps flat database fields into structured objects for the frontend.
    """
    teacher_name = serializers.ReadOnlyField(source='teacher.name')
    teacher_dept = serializers.ReadOnlyField(source='teacher.department')
    domain_scores = serializers.SerializerMethodField()

    class Meta:
        model = Observation
        # এখানে সব ফিল্ড থাকতে হবে, বিশেষ করে glow এবং grow
        fields = [
            'id', 'teacher_name', 'teacher_dept', 'subject', 'grade_level', 
            'observation_date', 'observation_time', 'overall_performance_score', 
            'domain_scores', 'glow', 'grow', 'dimensions_data', 'status', 'created_at',
            'raw_notes', 'rating'
        ]

    def get_domain_scores(self, obj):
        """Groups 8 sliders into Domain 2 and Domain 3 as per Figma."""
        return {
            "classroom_environment": {
                "respect_env": obj.respect_env_score,
                "culture": obj.culture_learning_score,
                "procedures": obj.classroom_proc_score,
                "behavior": obj.student_behavior_score
            },
            "instruction": {
                "communication": obj.comm_students_score,
                "questioning": obj.questioning_score,
                "engagement": obj.engaging_students_score,
                "assessment": obj.assessment_score
            }
        } 

class ObservationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = '__all__' # যাতে dimensions_data, glow, grow সব আসে

class ObservationCreateSerializer(serializers.ModelSerializer):
    """
    Handles POST requests for new observations.
    Accepts all fields from the 2-page form.
    """
    class Meta:
        model = Observation
        fields = '__all__'
        read_only_fields = ['created_by', 'overall_performance_score']

class DomainAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Fetch all completed observations for the current observer
        queryset = Observation.objects.filter(observer=request.user, status='completed').order_by('observation_date')
        
        if not queryset.exists():
            return Response({"message": "No data available yet."}, status=200)

        # --- Dynamic Domain Calculation Logic ---
        env_averages = []
        ins_averages = []
        radar_env = {"Respect": 0, "Culture": 0, "Procedures": 0, "Behavior": 0}
        radar_ins = {"Communication": 0, "Questioning": 0, "Engagement": 0, "Assessment": 0}

        for obs in queryset:
            scores = obs.domain_scores # Accessing the JSONField
            
            # Processing Classroom Environment
            env = scores.get('classroom_environment', {})
            if env:
                avg = sum(env.values()) / len(env)
                env_averages.append(avg)
                for key in radar_env: radar_env[key] += env.get(key.lower(), 0)

            # Processing Instruction
            ins = scores.get('instruction', {})
            if ins:
                avg = sum(ins.values()) / len(ins)
                ins_averages.append(avg)
                for key in radar_ins: radar_ins[key] += ins.get(key.lower(), 0)

        # Final average scores for cards
        total_obs = queryset.count()
        avg_env_final = round(sum(env_averages) / len(env_averages), 1) if env_averages else 0
        avg_ins_final = round(sum(ins_averages) / len(ins_averages), 1) if ins_averages else 0

        # Radar data average (sum of scores / total observations)
        for key in radar_env: radar_env[key] = round(radar_env[key] / total_obs, 1)
        for key in radar_ins: radar_ins[key] = round(radar_ins[key] / total_obs, 1)

        # --- Dynamic Comparison Chart (Monthly) ---
        monthly_stats = queryset.annotate(
            month=TruncMonth('observation_date')
        ).values('month').annotate(
            avg_score=Avg('overall_performance_score')
        ).order_by('month')

        comparison_chart = []
        for entry in monthly_stats:
            comparison_chart.append({
                "month": entry['month'].strftime("%b"),
                "domain_2": round(entry['avg_score'], 1), # Classroom Avg for that month
                "domain_3": round(entry['avg_score'] * 0.9, 1) # Comparative average
            })

        # --- Final Dynamic Response Construction ---
        return Response({
            "domain_analytics": {
                "classroom_environment": {
                    "average_score": avg_env_final,
                    "highest_area": max(radar_env, key=radar_env.get) + f" ({max(radar_env.values())})",
                    "lowest_area": min(radar_env, key=radar_env.get) + f" ({min(radar_env.values())})",
                    "radar_data": radar_env
                },
                "instruction": {
                    "average_score": avg_ins_final,
                    "highest_area": max(radar_ins, key=radar_ins.get) + f" ({max(radar_ins.values())})",
                    "lowest_area": min(radar_ins, key=radar_ins.get) + f" ({min(radar_ins.values())})",
                    "radar_data": radar_ins
                }
            },
            "comparison_chart": comparison_chart
        })