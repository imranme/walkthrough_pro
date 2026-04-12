from rest_framework import serializers
from .models import Teacher, Observation

class TeacherSerializer(serializers.ModelSerializer):
    """
    Serializer for Teacher profile management.
    Used for the 'Add Teacher' popup.
    """
    class Meta:
        model = Teacher
        fields = ['id', 'name', 'department', 'avg_score']

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
        fields = [
            'id', 'teacher_name', 'teacher_dept', 'subject', 'grade_level', 
            'observation_date', 'observation_time', 'overall_performance_score', 
            'domain_scores', 'glow', 'grow', 'dimensions_data', 'status', 'created_at'
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

class ObservationCreateSerializer(serializers.ModelSerializer):
    """
    Handles POST requests for new observations.
    Accepts all fields from the 2-page form.
    """
    class Meta:
        model = Observation
        fields = '__all__'
        read_only_fields = ['created_by', 'overall_performance_score']