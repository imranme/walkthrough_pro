from django.db import models
from django.contrib.auth.models import User

class Discussion(models.Model):
    """
    Main Discussion model representing questions or posts.
    Includes business logic for 'answered' status and global reply counts.
    """
    class Category(models.TextChoices):
        TTESS_GUIDANCE = "ttess_guidance", "T-TESS Guidance"
        BEST_PRACTICES = "best_practices", "Best Practices"
        FEATURE_QUESTIONS = "feature_questions", "Feature Questions"
        GENERAL = "general", "General"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="discussions")
    title = models.CharField(max_length=300)
    body = models.TextField()
    category = models.CharField(
        max_length=25, 
        choices=Category.choices, 
        default=Category.GENERAL,
        db_index=True  # Optimization for filtering by category
    )
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]  # Newest posts appear first

    @property
    def is_answered(self) -> bool:
        """A discussion is 'answered' if it has at least one answer."""
        return self.answers.exists()

    @property
    def reply_count(self) -> int:
        """Calculates total engagement (Answers + Replies to those answers)."""
        answer_count = self.answers.count()
        nested_replies = Reply.objects.filter(answer__discussion=self).count()
        return answer_count + nested_replies

class Answer(models.Model):
    """Direct answers to a specific discussion."""
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Reply(models.Model):
    """Sub-replies to a specific answer (threaded style)."""
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)