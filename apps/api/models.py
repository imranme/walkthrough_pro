from django.contrib.auth.models import User
from django.db import models

# ══════════════════════════════════════════════════════════════════════════════
# Teacher Model
# ══════════════════════════════════════════════════════════════════════════════

class Teacher(models.Model):
    name        = models.CharField(max_length=150)
    school      = models.CharField(max_length=200, blank=True, default="")
    subject     = models.CharField(max_length=100, blank=True, default="")
    grade_level = models.CharField(max_length=50, blank=True, default="")
    created_by  = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teachers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("name", "created_by")]

    def __str__(self):
        return f"{self.name} · {self.school}"


# ══════════════════════════════════════════════════════════════════════════════
# Observation Model (The AI Core)
# ══════════════════════════════════════════════════════════════════════════════

class Observation(models.Model):
    class Rating(models.TextChoices):
        DISTINGUISHED      = "distinguished",      "Distinguished"
        ACCOMPLISHED       = "accomplished",       "Accomplished"
        PROFICIENT         = "proficient",         "Proficient"
        DEVELOPING         = "developing",         "Developing"
        IMPROVEMENT_NEEDED = "improvement_needed", "Improvement Needed"

    teacher    = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="observations")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="observations")

    # User Input
    raw_notes = models.TextField(help_text="Rough notes during walkthrough.")
    rating    = models.CharField(
        max_length=25,
        choices=Rating.choices,
        default=Rating.PROFICIENT,
        db_index=True,
    )

    # AI Results
    ai_evidence   = models.TextField(blank=True, default="")
    glow          = models.TextField(blank=True, default="")
    grow          = models.TextField(blank=True, default="")
    domain_scores = models.JSONField(default=dict, blank=True)

    # Metadata
    observation_date = models.DateField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Obs: {self.teacher.name} | {self.get_rating_display()}"