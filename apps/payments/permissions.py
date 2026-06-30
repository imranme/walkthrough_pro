"""
apps/payments/permissions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Web  → Django controls (Stripe)
Mobile → RevenueCat controls (Django pass করে)
"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

TRIAL_EXPIRED_RESPONSE = {
    "error": "trial_expired",
    "message": "Your 5-day trial has expired. Please upgrade to continue.",
    "action": "SHOW_PAYMENT_WALL",
    "upgrade_url": "https://walkthroughpro.app/pricing",
}

NO_SUBSCRIPTION_RESPONSE = {
    "error": "no_subscription",
    "message": "No subscription found. Please start your free trial.",
    "upgrade_url": "https://walkthroughpro.app/pricing",
}

# Added missing variables to fix the observations/views.py import crash 🎯
DASHBOARD_FORBIDDEN = {"error": "Access restricted."}
WEB_TRIAL_EXPIRED_RESPONSE = TRIAL_EXPIRED_RESPONSE


def _get_sub(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.subscription
    except Exception:
        return None


def _is_mobile_request(request) -> bool:
    return (
        request.headers.get("X-Client-Type", "").lower() == "mobile"
        or request.META.get("HTTP_X_CLIENT_TYPE", "").lower() == "mobile"
    )


class IsSubscriptionActive(BasePermission):
    """
    Web:
      Superuser/Staff → always pass
      Trial active    → pass
      Pro active      → pass
      Expired         → 403
      No sub          → 403

    Mobile:
      Always pass → RevenueCat handles paywall
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # Superuser/Staff → always pass
        if user.is_superuser or user.is_staff:
            return True

        # Mobile → RevenueCat handles, just pass
        if _is_mobile_request(request):
            return True

        # Web → Django controls
        sub = _get_sub(user)
        if not sub:
            raise PermissionDenied(detail=NO_SUBSCRIPTION_RESPONSE)

        if getattr(sub, "is_fully_active", False):
            return True

        raise PermissionDenied(detail=TRIAL_EXPIRED_RESPONSE)


class IsDashboardUser(BasePermission):
    """
    New Rule: Allows ANY authenticated user (including observers/free/expired users)
    to view the dashboard stats without restriction.
    """

    def has_permission(self, request, view):
        # Just check if the user is logged in
        return bool(request.user and request.user.is_authenticated)


# Aliases
IsAppUser = IsSubscriptionActive
# IsDashboardUser is now independent and open to everyone 🔓