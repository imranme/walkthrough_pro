# from rest_framework import serializers
# from .models import Teacher, Observation

# # =======================================================================
# # 1. TEACHER SERIALIZERS
# # =======================================================================

# class TeacherSerializer(serializers.ModelSerializer):
#     avg_score = serializers.FloatField(read_only=True)
#     observations_count = serializers.IntegerField(source='obs_count', read_only=True)
#     last_observation = serializers.SerializerMethodField()

#     class Meta:
#         model = Teacher
#         fields = ['id', 'name', 'department', 'avg_score', 'observations_count', 'last_observation']
#         read_only_fields = ['created_by']

#     def get_last_observation(self, obj):
#         # 'observations' related name ব্যবহার করে শেষ অবজেক্ট ট্র্যাক করা
#         last_obs = obj.observations.order_by('-observation_date').first()
#         if last_obs and last_obs.observation_date:
#             return last_obs.observation_date.strftime("%B %d, %Y")
#         return "No data"


# class TeacherSimpleSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Teacher
#         fields = ['id', 'name']


# # =======================================================================
# # 2. OBSERVATION SERIALIZERS (READ & CREATE FIXED Layers)
# # =======================================================================

# class ObservationReadSerializer(serializers.ModelSerializer):
#     """
#     Detailed view of an Observation for the UI.
#     Maps flat database fields into structured objects for the frontend.
#     """
#     teacher_name = serializers.ReadOnlyField(source='teacher.name', default="Teacher")
#     teacher_dept = serializers.ReadOnlyField(source='teacher.department', default="N/A")
#     domain_scores = serializers.SerializerMethodField()

#     class Meta:
#         model = Observation
#         fields = '__all__'  # সব কলাম (glow, grow, dimensions_data) সহ রিড হবে

#     def to_representation(self, instance):
#         """
#         সিরিয়ালাইজার আউটপুটে Figma ডিজাইনের ডাইনামিক 'domain_scores' ইনজেক্ট করার সেফ মেথড
#         """
#         representation = super().to_representation(instance)
#         representation['domain_scores'] = self.get_domain_scores(instance)
#         return representation

#     def get_domain_scores(self, obj):
#         """Groups 8 sliders into Domain 2 and Domain 3 categories as per Figma."""
#         return {
#             "classroom_environment": {
#                 "respect_env": getattr(obj, 'respect_env_score', 0.0) or 0.0,
#                 "culture": getattr(obj, 'culture_learning_score', 0.0) or 0.0,
#                 "procedures": getattr(obj, 'classroom_proc_score', 0.0) or 0.0,
#                 "behavior": getattr(obj, 'student_behavior_score', 0.0) or 0.0
#             },
#             "instruction": {
#                 "communication": getattr(obj, 'comm_students_score', 0.0) or 0.0,
#                 "questioning": getattr(obj, 'questioning_score', 0.0) or 0.0,
#                 "engagement": getattr(obj, 'engaging_students_score', 0.0) or 0.0,
#                 "assessment": getattr(obj, 'assessment_score', 0.0) or 0.0
#             }
#         }


# class ObservationCreateSerializer(serializers.ModelSerializer):
#     """
#     Handles POST requests for new observations.
#     CRITICAL FIX: Explicitly ignore non-model input parameters during DB write maps.
#     """
#     # ওয়ান-ওয়ে ট্র্যাক সেট করা হলো যেন ডাটাবেজ কলাম মনে করে ক্র্যাশ না করে
#     teacher_name = serializers.CharField(read_only=True, required=False)
#     selected_domains = serializers.JSONField(write_only=True, required=False)

#     class Meta:
#         model = Observation
#         fields = '__all__'
#         read_only_fields = ['created_by', 'overall_performance_score']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # মেটা ডিকশনারি ভ্যালিডেশনের আগে selected_domains ফিল্ডটি ডাইনামিকালি ম্যাপে ইনজেক্ট করা হলো
#         self.fields['selected_domains'] = serializers.JSONField(write_only=True, required=False)

#     def create(self, validated_data):
#         # ডাটাবেজে অবজেক্ট ক্রিয়েট করার ঠিক আগ মুহূর্তে নন-মডেল ফিল্ডগুলো পপ করে ড্রপ করা হলো
#         validated_data.pop('teacher_name', None)
#         validated_data.pop('selected_domains', None)
#         return super().create(validated_data) 


from rest_framework import serializers
from .models import Teacher, Observation


# ═══════════════════════════════════════════════════════════════════════
# 1. TEACHER SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════

class TeacherSerializer(serializers.ModelSerializer):
    avg_score          = serializers.FloatField(read_only=True)
    observations_count = serializers.IntegerField(source='obs_count', read_only=True)
    last_observation   = serializers.SerializerMethodField()

    class Meta:
        model        = Teacher
        fields       = ['id', 'name', 'department', 'avg_score', 'observations_count', 'last_observation']
        read_only_fields = ['created_by']

    def get_last_observation(self, obj):
        last_obs = obj.observations.order_by('-observation_date').first()
        if last_obs and last_obs.observation_date:
            return last_obs.observation_date.strftime("%B %d, %Y")
        return "No data"


class TeacherSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Teacher
        fields = ['id', 'name']


# ═══════════════════════════════════════════════════════════════════════
# 2. OBSERVATION SERIALIZERS
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