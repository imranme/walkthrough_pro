from django.db import models
from django.conf import settings
from django.db.models import Avg

class Teacher(models.Model):
    name = models.CharField(max_length=150)
    department = models.CharField(max_length=100)
    subject = models.CharField(max_length=100, blank=True)
    grade_level = models.CharField(max_length=50, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.department}"

    @property
    def avg_score(self):
        # Teacher-er shob observations er average score calculate kore
        avg = self.observations.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
        return round(avg, 1) if avg else 0.0

    @property
    def observation_count(self):
        # Teacher-er total koiti observation hoyeche sheta count kore
        return self.observations.count()

class Observation(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="observations")
    raw_notes = models.TextField()
    rating = models.CharField(max_length=50) # e.g. Accomplished, Proficient
    overall_performance_score = models.FloatField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Latest observation gulo shobar upore dekhanor jonno
        ordering = ['-created_at']