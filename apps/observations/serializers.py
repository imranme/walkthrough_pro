from rest_framework import serializers
from django.db.models import Avg
from .models import Teacher, Observation

# ═══════════════════════════════════════════════════════════════════════
# 1. TEACHER SERIALIZERS (FIXED)
# ═══════════════════════════════════════════════════════════════════════

class TeacherSerializer(serializers.ModelSerializer):
    avg_score          = serializers.SerializerMethodField()
    observations_count = serializers.SerializerMethodField()
    last_observation   = serializers.SerializerMethodField()

    class Meta:
        model        = Teacher
        fields       = ['id', 'name', 'department', 'avg_score', 'observations_count', 'last_observation']
        read_only_fields = ['created_by']

    def get_observations_count(self, obj):
        # রিলেশনশিপ ছাড়া সরাসরি teacher_name টেক্সট ফিল্ড দিয়ে কাউন্ট
        return Observation.objects.filter(teacher_name=obj.name).count()

    def get_avg_score(self, obj):
        # সরাসরি teacher_name দিয়ে অবজারভেশনের গড় স্কোর বের করা
        avg = Observation.objects.filter(teacher_name=obj.name).aggregate(
            avg_val=Avg('overall_performance_score')
        )['avg_val']
        return round(avg, 1) if avg else 0.0

    def get_last_observation(self, obj):
        # obj.observations এর বদলে সরাসরি কুয়েরি করে শেষ ডেটটি বের করা
        last_obs = Observation.objects.filter(teacher_name=obj.name).order_by('-observation_date', '-created_at').first()
        if last_obs and last_obs.observation_date:
            return last_obs.observation_date.strftime("%B %d, %Y")
        elif last_obs:
            return last_obs.created_at.strftime("%B %d, %Y")
        return "No data"


class TeacherSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Teacher
        fields = ['id', 'name', 'department']


# ═══════════════════════════════════════════════════════════════════════
# 2. OBSERVATION SERIALIZERS (READ & CREATE)
# ═══════════════════════════════════════════════════════════════════════

class ObservationReadSerializer(serializers.ModelSerializer):
    """
    Clean observation response — only fields the app actually needs.
    """
    class Meta:
        model  = Observation
        fields = [
            'id',
            'teacher_name',
            'subject',
            'grade_level',
            'observation_date',
            'observation_time',
            'domain_2_selected',
            'domain_3_selected',
            'raw_notes',
            'overall_performance_score',
            'rating',
            'status',
            'glow',
            'grow',
            'dimensions_data',
            'created_at',
            'updated_at',
            'created_by',
        ]


class ObservationCreateSerializer(serializers.ModelSerializer):
    """
    Handles POST requests.
    selected_domains is write-only — used for AI only, not saved to DB.
    """
    selected_domains = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model        = Observation
        fields       = '__all__'
        read_only_fields = ['created_by', 'overall_performance_score']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['selected_domains'] = serializers.JSONField(write_only=True, required=False)

    def create(self, validated_data):
        validated_data.pop('selected_domains', None)
        return super().create(validated_data)