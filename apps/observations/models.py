from django.db import models
from django.conf import settings
from django.db.models import Avg

class Teacher(models.Model):
    """
    Represents a Teacher profile. 
    Stores basic professional identity data.
    """
    name = models.CharField(max_length=150, help_text="Full name of the teacher.")
    department = models.CharField(max_length=100, help_text="Academic department.")
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.department})"

    @property
    def avg_score(self):
        avg = self.observations.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
        return round(avg, 1) if avg else 0.0

class Observation(models.Model):
    """
    Captures classroom observation data with administrative and rubric-based scoring.
    """
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('completed', 'Completed'),
    )

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="observations")
    
    # --- Page 1: Contextual Data ---
    # Added null=True, blank=True to avoid migration errors with existing data
    subject = models.CharField(max_length=100, null=True, blank=True)
    grade_level = models.CharField(max_length=50, null=True, blank=True)
    observation_date = models.DateField(null=True, blank=True)
    observation_time = models.TimeField(null=True, blank=True)

    # --- Page 2: Rubric Scores ---
    respect_env_score = models.FloatField(default=0.0)
    culture_learning_score = models.FloatField(default=0.0)
    classroom_proc_score = models.FloatField(default=0.0)
    student_behavior_score = models.FloatField(default=0.0)

    comm_students_score = models.FloatField(default=0.0)
    questioning_score = models.FloatField(default=0.0)
    engaging_students_score = models.FloatField(default=0.0)
    assessment_score = models.FloatField(default=0.0)

    # --- qualitative Analysis ---
    raw_notes = models.TextField(null=True, blank=True)
    overall_performance_score = models.FloatField(default=0.0)
    rating = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')

    # AI Results
    glow = models.TextField(null=True, blank=True)
    grow = models.TextField(null=True, blank=True)
    dimensions_data = models.JSONField(default=list, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.teacher.name} - {self.observation_date}"