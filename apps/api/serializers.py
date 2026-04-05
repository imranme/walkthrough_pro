from rest_framework import serializers
from .models import Observation, Teacher
from django.contrib.auth.models import User

class TeacherSerializer(serializers.ModelSerializer):
    observation_count = serializers.SerializerMethodField()
    avg_score         = serializers.SerializerMethodField()

    class Meta:
        model  = Teacher
        fields = ("id", "name", "school", "subject", "grade_level", "observation_count", "avg_score")

    def get_observation_count(self, obj):
        return obj.observations.count()

    def get_avg_score(self, obj):
        if not observations.exists(): 
            return 0

        # Simple Logic: mapping rating strings to numbers
        mapping = {'distinguished': 4, 'accomplished': 3, 'proficient': 2, 'developing': 1, 'improvement_needed': 0}
        scores = [mapping.get(o.rating, 2) for o in observations]
        return round(sum(scores) / len(scores), 2)

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)

# --- Observation Serializers ---
class ObservationReadSerializer(serializers.ModelSerializer):
    rating_display = serializers.CharField(source="get_rating_display", read_only=True)
    class Meta:
        model = Observation
        fields = '__all__'

class ObservationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = ("id", "teacher", "raw_notes", "rating", "observation_date")

    def create(self, validated_data):
        # AI Engine (ai_service.py) ekhane call hobe
        from .ai_service import generate_feedback 
        
        validated_data["created_by"] = self.context["request"].user
        
        # AI ke notes pathano
        feedback = generate_feedback(validated_data["raw_notes"], validated_data["rating"])
        
        # AI theke pawa results model field e fill kora
        validated_data.update(feedback)
        return super().create(validated_data)