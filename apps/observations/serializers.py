from rest_framework import serializers
from .models import Teacher, Observation

class TeacherSerializer(serializers.ModelSerializer):
    """
    Serializer for the Teacher model.
    Includes calculated fields for dashboard metrics.
    """
    avg_score = serializers.ReadOnlyField()
    observation_count = serializers.ReadOnlyField()

    class Meta:
        model = Teacher
        fields = [
            'id', 'name', 'department', 'subject', 
            'grade_level', 'avg_score', 'observation_count'
        ]

class ObservationReadSerializer(serializers.ModelSerializer):
    """
    Serializer to provide a detailed view of an Observation.
    Flattens data from the related Teacher model for UI consistency (Dashboard & Detail).
    """
    # Teacher related details (Read-only from related Teacher object)
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    department = serializers.CharField(source='teacher.department', read_only=True)
    subject = serializers.CharField(source='teacher.subject', read_only=True)
    grade_level = serializers.CharField(source='teacher.grade_level', read_only=True)
    
    # Formatted Date and Time strings based on Figma requirements
    # Example: "April 07, 2026" and "09:41 AM"
    date = serializers.DateTimeField(source='created_at', format="%B %d, %Y", read_only=True)
    time = serializers.DateTimeField(source='created_at', format="%I:%M %p", read_only=True)

    class Meta:
        model = Observation
        fields = [
            'id', 'teacher_name', 'department', 'subject', 
            'grade_level', 'date', 'time', 'raw_notes', 
            'rating', 'overall_performance_score'
        ]

class ObservationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for handling Observation creation.
    Focuses only on user-input fields.
    """
    class Meta:
        model = Observation
        fields = ['teacher', 'raw_notes', 'rating', 'overall_performance_score']