from datetime import timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Subscription(models.Model):
    """
    Handles user subscription plans, including free trial and professional tiers.
    Integrates with Stripe for subscription tracking.
    """
    PLAN_CHOICES = (
        ('free_trial',   'Free Trial'),
        ('professional', 'Professional'),
    )
    STATUS_CHOICES = (
        ('trial',   'Trial'),
        ('active',  'Active'),
        ('expired', 'Expired'),
    )

    # --- Core Fields ---
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='subscription'
    )
    plan_type = models.CharField(
        max_length=20, 
        choices=PLAN_CHOICES, 
        default='free_trial'
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='trial'
    )

    # --- Trial Period Tracking ---
    trial_start_date = models.DateTimeField(default=timezone.now)
    trial_end_date   = models.DateTimeField(null=True, blank=True)

    # --- External Integration ---
    stripe_subscription_id = models.CharField(
        max_length=120, 
        blank=True, 
        null=True
    )

    def save(self, *args, **kwargs):
        """Auto-sets trial_end_date to 5 days after start if not provided."""
        if not self.trial_end_date:
            self.trial_end_date = self.trial_start_date + timedelta(days=5)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """
        Determines if the user currently has access to features.
        Returns True if:
        1. User has an active Professional plan.
        2. User is within their 5-day Free Trial period.
        """
        if self.plan_type == 'professional' and self.status == 'active':
            return True
        if self.plan_type == 'free_trial' and timezone.now() <= self.trial_end_date:
            return True
        return False

    def __str__(self):
        return f"{self.user.email} | {self.plan_type} | {self.status}"


class Invoice(models.Model):
    """
    Stores historical billing data synced from Stripe.
    Used for displaying payment history in the user's dashboard.
    """
    STATUS_CHOICES = (
        ('paid',   'Paid'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='invoices'
    )
    stripe_invoice_id = models.CharField(max_length=120, unique=True)
    amount_cents      = models.PositiveIntegerField()
    status            = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='paid'
    )
    invoice_date      = models.DateField()
    invoice_pdf_url   = models.URLField(blank=True, default='')
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-invoice_date']
        db_table = 'invoices'

    @property
    def amount_display(self):
        """Converts amount_cents to a formatted dollar string (e.g., $9.99)."""
        return f"${self.amount_cents / 100:.2f}"

    def __str__(self):
        return f"{self.user.email} | {self.stripe_invoice_id} | {self.amount_display}"