from rest_framework import serializers
from .models import Observation, Teacher

class TeacherSerializer(serializers.ModelSerializer):
    # Figma Table: Observations, Avg Score কলামের জন্য
    observation_count = serializers.SerializerMethodField()
    avg_score         = serializers.SerializerMethodField()

    class Meta:
        model  = Teacher
        fields = ("id", "name", "department", "subject", "grade_level", "observation_count", "avg_score")

    def get_observation_count(self, obj):
        return obj.observations.count()

    def get_avg_score(self, obj):
        observations = obj.observations.all()
        if not observations.exists(): 
            return 0.0
        # Figma ৩.৩ গড় স্কোরের লজিক
        avg = sum([obs.overall_performance_score for obs in observations]) / observations.count()
        return round(avg, 1)

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)

class ObservationReadSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    rating_display = serializers.CharField(source="get_rating_display", read_only=True)
    
    class Meta:
        model = Observation
        fields = '__all__'

class ObservationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = ("id", "teacher", "raw_notes", "rating", "observation_date", "overall_performance_score")

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        # এখানে AI সার্ভিস কল করে feedback (glow/grow) আপডেট করা যায়
        return super().create(validated_data)