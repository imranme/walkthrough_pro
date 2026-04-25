from django.contrib import admin
from .models import Invoice, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = (
        "user", "plan_type", "status",
        "trial_days_remaining", "is_pro_active",
        "trial_end_date", "pro_end_date", "created_at",
    )
    list_filter   = ("plan_type", "status")
    search_fields = ("user__email", "user__username", "stripe_customer_id")
    readonly_fields = (
        "is_trial_active", "is_trial_expired", "is_pro_active",
        "is_fully_active", "trial_days_remaining", "observations_limit",
        "created_at", "updated_at",
    )
    actions = ["sync_status_action"]

    @admin.action(description="Sync subscription status")
    def sync_status_action(self, request, queryset):
        for sub in queryset:
            sub.sync_status()
        self.message_user(request, f"{queryset.count()} subscriptions synced.")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ("user", "invoice_number", "amount_display", "status", "invoice_date")
    list_filter   = ("status", "currency")
    search_fields = ("user__email", "stripe_invoice_id")
    readonly_fields = ("amount_display", "invoice_number", "created_at")