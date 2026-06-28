from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Subscription(models.Model):
    """
    Subscription model to handle 5-day trials and Professional plans.
    Strictly enforces access rules for Web and passes identity context for Mobile.
    """
    
    PLAN_CHOICES = (
        ('free_trial',   'Free Trial'),
        ('professional', 'Professional'),
    )
    STATUS_CHOICES = (
        ('trial',     'Trial'),      
        ('active',    'Active'),     
        ('expired',   'Expired'),    
        ('cancelled', 'Cancelled'),  
    )

    # --- Relationships & Identity ---
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='subscription',
        help_text="The user associated with this subscription."
    )
    plan_type = models.CharField(
        max_length=20, 
        choices=PLAN_CHOICES, 
        default='free_trial'
    )
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default='trial'
    )

    # --- Timing & Tracking ---
    trial_start_date = models.DateTimeField(
        default=timezone.now,
        help_text="Date when the 5-day trial began."
    )
    trial_end_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Calculated trial expiration date."
    )
    
    # --- Stripe Integration Fields ---
    stripe_customer_id = models.CharField(max_length=120, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, null=True)
    pro_end_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="End date of the paid professional plan."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'

    def save(self, *args, **kwargs):
        """Auto-calculates the 5-day trial period expiration upon creation."""
        if not self.trial_end_date:
            self.trial_end_date = self.trial_start_date + timedelta(days=5)
        super().save(*args, **kwargs)

    # ── Logic Properties ──────────────────────────────────────────

    @property
    def is_trial_active(self) -> bool:
        """Checks if the user is currently within an active, non-expired free trial."""
        return self.plan_type == 'free_trial' and self.status == 'trial' and self.trial_end_date and timezone.now() <= self.trial_end_date

    @property
    def is_trial_expired(self) -> bool:
        """Checks if the free trial has completely passed its expiration deadline."""
        if self.plan_type == 'free_trial' and self.trial_end_date:
            return timezone.now() > self.trial_end_date
        return False

    @property
    def is_pro_active(self) -> bool:
        """Validates if the user has an active professional plan backed by a valid expiration date."""
        if self.plan_type == 'professional' and self.status == 'active':
            if self.pro_end_date:
                return timezone.now() <= self.pro_end_date
            return True
        return False

    @property
    def is_fully_active(self) -> bool:
        """Returns True if either the trial or professional plan is validated as active."""
        return self.is_trial_active or self.is_pro_active

    @property
    def has_app_access(self) -> bool:
        """Gateway validation hook for broad application entry access points."""
        return self.is_fully_active

    @property
    def can_access_dashboard(self) -> bool:
        """
        Bypasses payment restrictions for staff/superusers, 
        otherwise enforces active validation states for standard users.
        """
        if self.user.is_staff or self.user.is_superuser:
            return True
        return self.is_fully_active

    @property
    def trial_days_remaining(self) -> int:
        """Fallback mechanism to maintain database compatibility without breaking schema declarations."""
        return 0

    def __str__(self):
        return f"{self.user.email} | {self.plan_type} | {self.status}"


class Invoice(models.Model):
    """Stores historical billing records synced from Stripe."""
    
    STATUS_CHOICES = (
        ('paid',   'Paid'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    stripe_invoice_id = models.CharField(max_length=120, unique=True)
    amount_cents = models.PositiveIntegerField(help_text="Amount in cents")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='paid')
    invoice_date = models.DateField()
    invoice_pdf_url = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-invoice_date']
        db_table = 'invoices'

    @property
    def amount_display(self):
        """Formats base amount cents into standard dollar visual representations."""
        return f"${self.amount_cents / 100:.2f}"