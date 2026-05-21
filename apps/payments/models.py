from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Subscription(models.Model):
    """
    Subscription model to handle 5-day trials and Professional plans.
    Strictly enforces role-based access.
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
        """Auto-calculate 5-day trial period upon creation."""
        if not self.trial_end_date:
            self.trial_end_date = self.trial_start_date + timedelta(days=5)
        super().save(*args, **kwargs)

    # ── Logic Properties ──────────────────────────────────────────

    @property
    def is_trial_active(self) -> bool:
        """Check if user is currently within the 5-day trial window."""
        return self.plan_type == 'free_trial' and timezone.now() <= self.trial_end_date

    @property
    def is_pro_active(self) -> bool:
        """Check if user has a paid and active professional subscription."""
        return self.plan_type == 'professional' and self.status == 'active'

    @property
    def is_fully_active(self) -> bool:
        """True if the user has any form of valid access (Trial or Pro)."""
        return self.is_trial_active or self.is_pro_active

    @property
    def has_app_access(self) -> bool:
        return self.is_fully_active

    @property
    def can_access_dashboard(self) -> bool:
        if self.user.is_staff or self.user.is_superuser:
            return self.is_fully_active
        return False

    @property
    def trial_days_remaining(self):
        """FIXED: Now points to trial_end_date instead of trial_end"""
        if self.trial_end_date:
            remaining = (self.trial_end_date - timezone.now()).days
            return max(0, remaining)
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
        return f"${self.amount_cents / 100:.2f}" 


# from django.contrib.auth import get_user_model
# from django.db import models
# from django.utils import timezone
# from datetime import timedelta

# User = get_user_model()

# class Subscription(models.Model):
#     """
#     Subscription model to handle 5-day trials and Professional plans.
#     Strictly enforces role-based access.
#     """
    
#     PLAN_CHOICES = (
#         ('free_trial',   'Free Trial'),
#         ('professional', 'Professional'),
#     )
#     STATUS_CHOICES = (
#         ('trial',     'Trial'),      
#         ('active',    'Active'),     
#         ('expired',   'Expired'),    
#         ('cancelled', 'Cancelled'),  
#     )

#     # --- Relationships & Identity ---
#     user = models.OneToOneField(
#         User, 
#         on_delete=models.CASCADE, 
#         related_name='subscription',
#         help_text="The user associated with this subscription."
#     )
#     plan_type = models.CharField(
#         max_length=20, 
#         choices=PLAN_CHOICES, 
#         default='free_trial'
#     )
#     status = models.CharField(
#         max_length=15, 
#         choices=STATUS_CHOICES, 
#         default='trial'
#     )

#     # --- Timing & Tracking ---
#     trial_start_date = models.DateTimeField(
#         default=timezone.now,
#         help_text="Date when the 5-day trial began."
#     )
#     trial_end_date = models.DateTimeField(
#         null=True, 
#         blank=True,
#         help_text="Calculated trial expiration date."
#     )
    
#     # --- Stripe Integration Fields ---
#     stripe_customer_id = models.CharField(max_length=120, blank=True, null=True)
#     stripe_subscription_id = models.CharField(max_length=120, blank=True, null=True)
#     pro_end_date = models.DateTimeField(
#         null=True, 
#         blank=True,
#         help_text="End date of the paid professional plan."
#     )

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'subscriptions'
#         verbose_name = 'Subscription'
#         verbose_name_plural = 'Subscriptions'

#     def save(self, *args, **kwargs):
#         """
#         FIXED: প্রতিবার সেভ করার সময় স্টার্ট ডেটের ওপর ভিত্তি করে 
#         এন্ড ডেট নতুন করে ৫ দিন রি-ক্যালকুলেট করবে। 
#         এতে অ্যাডমিন প্যানেলে ডেট পরিবর্তন করলে সাথে সাথে রিমেইনিং ডেজ আপডেট হবে।
#         """
#         if self.plan_type == 'free_trial':
#             self.trial_end_date = self.trial_start_date + timedelta(days=5)
#         super().save(*args, **kwargs)

#     # ── Logic Properties ──────────────────────────────────────────

#     @property
#     def is_trial_active(self) -> bool:
#         """Check if user is currently within the 5-day trial window."""
#         return self.plan_type == 'free_trial' and timezone.now() <= self.trial_end_date

#     @property
#     def is_pro_active(self) -> bool:
#         """Check if user has a paid and active professional subscription."""
#         return self.plan_type == 'professional' and self.status == 'active'

#     @property
#     def is_fully_active(self) -> bool:
#         """True if the user has any form of valid access (Trial or Pro)."""
#         return self.is_trial_active or self.is_pro_active

#     @property
#     def has_app_access(self) -> bool:
#         return self.is_fully_active

#     @property
#     def can_access_dashboard(self) -> bool:
#         if self.user.is_staff or self.user.is_superuser:
#             return self.is_fully_active
#         return False

#     @property
#     def trial_days_remaining(self):
#         """FIXED: points to trial_end_date instead of trial_end"""
#         if self.trial_end_date:
#             remaining = (self.trial_end_date - timezone.now()).days
#             return max(0, remaining)
#         return 0

#     def __str__(self):
#         return f"{self.user.email} | {self.plan_type} | {self.status}"


# class Invoice(models.Model):
#     """Stores historical billing records synced from Stripe."""
    
#     STATUS_CHOICES = (
#         ('paid',   'Paid'),
#         ('failed', 'Failed'),
#     )

#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
#     stripe_invoice_id = models.CharField(max_length=120, unique=True)
#     amount_cents = models.PositiveIntegerField(help_text="Amount in cents")
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='paid')
#     invoice_date = models.DateField()
#     invoice_pdf_url = models.URLField(blank=True, default='')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['-invoice_date']
#         db_table = 'invoices'

#     @property
#     def amount_display(self):
#         return f"${self.amount_cents / 100:.2f}"