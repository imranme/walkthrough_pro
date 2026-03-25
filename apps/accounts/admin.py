from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # Admin panel-e ja ja column dekhabe
    list_display  = ("user", "subscription_status", "stripe_customer_id", "created_at")
    # Side-e filter option thakbe
    list_filter   = ("subscription_status",)
    # Search box-e ja diye khonja jabe
    search_fields = ("user__username", "user__email", "stripe_customer_id")
    # Egulo edit kora jabe na, shudhu dekha jabe
    readonly_fields = ("created_at", "updated_at")