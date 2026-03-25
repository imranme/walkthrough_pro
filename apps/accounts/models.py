from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# ══════════════════════════════════════════════════════════════════════════════
# Profile Model
# ══════════════════════════════════════════════════════════════════════════════

class Profile(models.Model):
    class SubscriptionStatus(models.TextChoices):
        FREE      = "free",      "Free"
        PRO       = "pro",       "Pro"
        CANCELLED = "cancelled", "Cancelled"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.FREE,
        db_index=True,
    )
    stripe_customer_id     = models.CharField(max_length=120, blank=True, null=True, unique=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profile"

    def __str__(self):
        return f"{self.user.username} [{self.subscription_status}]"

    @property
    def is_pro(self) -> bool:
        return self.subscription_status == self.SubscriptionStatus.PRO


# Automation: User toiri holei Profile auto-create hobe
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()