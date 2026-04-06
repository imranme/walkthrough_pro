from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg

# ══════════════════════════════════════════════════════════════════════════════
# Teacher Model (Figma: Teachers View & Add Teacher Modal)
# ══════════════════════════════════════════════════════════════════════════════

class Teacher(models.Model):
    # Figma: Add Teacher Modal (Screenshot: 003425)
    name        = models.CharField(max_length=150)
    department  = models.CharField(max_length=100, )
    
    # Figma: Observation Form dropdowns (Screenshot: 004409)
    subject     = models.CharField(max_length=100, blank=True, default="")
    grade_level = models.CharField(max_length=50,  blank=True, default="")

    # Additional Meta
    school      = models.CharField(max_length=200, blank=True, default="")
    email       = models.EmailField(blank=True, default="")
    
    # Ownership
    created_by  = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teachers")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering        = ["name"]
        # unique_together = [("name", "created_by")]
        pass 

    # ── Dynamic Properties for Figma Table (Screenshot: 003425) ──

    @property
    def observation_count(self):
        """Table: 'Observations' column"""
        return self.observations.count()

    @property
    def avg_score(self):
        """Table: 'Avg Score' column"""
        # Figma score 3.4/4 calculation
        avg = self.observations.aggregate(Avg('overall_performance_score'))['overall_performance_score__avg']
        return round(avg, 1) if avg else 0.0

    @property
    def last_observation_date(self):
        """Table: 'Last Observation' column"""
        last_obs = self.observations.order_by('-observation_date').first()
        return last_obs.observation_date if last_obs else None

    def __str__(self):
        return f"{self.name} · {self.department}"


# ══════════════════════════════════════════════════════════════════════════════
# Observation Model (The AI Core - Figma: AI Coaching Results)
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

    # User Input (Screenshot: Observation Form)
    raw_notes = models.TextField(help_text="Rough notes during walkthrough.")
    rating    = models.CharField(
        max_length=25,
        choices=Rating.choices,
        default=Rating.PROFICIENT,
        db_index=True,
    )

    overall_performance_score = models.FloatField(default=0.0) 
    
    # 'AI Coaching Output' sections
    ai_evidence   = models.TextField(blank=True, default="")
    glow          = models.TextField(blank=True, default="")
    grow          = models.TextField(blank=True, default="")
    
    # Radar Chart & Domain Analytics data
    domain_scores = models.JSONField(default=dict, blank=True)

    # Metadata (Screenshot: History)
    observation_date = models.DateField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Obs: {self.teacher.name} | {self.get_rating_display()}"