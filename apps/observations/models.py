from django.db import models
from django.conf import settings
from django.db.models import Avg


class Teacher(models.Model):

    name = models.CharField(max_length=150, help_text="Full name of the teacher.")
    department = models.CharField(max_length=100, help_text="Academic department.")
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def avg_score(self):
        avg = self.observations.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
        return round(avg, 1) if avg else 0.0

class Observation(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('completed', 'Completed'),
    )

    teacher_name = models.CharField(max_length=255, null=True, blank=True, help_text="Selected teacher name from dropdown")
    subject = models.CharField(max_length=100, null=True, blank=True)
    grade_level = models.CharField(max_length=50, null=True, blank=True)
    observation_date = models.DateField(null=True, blank=True)
    observation_time = models.TimeField(null=True, blank=True)

    #domain-specific fields
    domain_2_selected = models.BooleanField(default=True)
    domain_3_selected = models.BooleanField(default=True)

    # --- Qualitative Analysis (Observation Notes) ---
    raw_notes = models.TextField(null=True, blank=True, help_text="Text written inside Observation Notes box")

    # AI Outputs 
    overall_performance_score = models.FloatField(default=0.0)
    rating = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    glow = models.TextField(null=True, blank=True)
    grow = models.TextField(null=True, blank=True)
    dimensions_data = models.JSONField(default=list, blank=True)
    
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.teacher_name} - {self.observation_date}"