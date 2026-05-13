from django.utils import timezone
from rest_framework.permissions import BasePermission
from django.http import JsonResponse

# --- Standard Error Responses ---

TRIAL_EXPIRED_RESPONSE = {
    "error": "trial_expired",
    "message": "Your 5-day trial has expired. Please upgrade to a Professional plan to continue.",
    "upgrade_url": "https://walkthroughpro.app/pricing",
}

NO_SUBSCRIPTION_RESPONSE = {
    "error": "no_subscription",
    "message": "No active subscription record was found for this account.",
}

DASHBOARD_FORBIDDEN = {
    "error": "access_denied",
    "message": "Access Denied: The Analytics Dashboard is reserved for Admin users only.",
}

# --- Internal Helper Functions ---

def _get_sub(user):
    """Retrieves the subscription object for a given user safely."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.subscription
    except Exception:
        return None

def _is_admin(user) -> bool:
    """Checks if the user has Admin/Staff privileges."""
    return bool(user and (user.is_staff or user.is_superuser))

# ══════════════════════════════════════════════════════════════════════
# 1. IsAppUser (Permission Class)
# ══════════════════════════════════════════════════════════════════════

class IsAppUser(BasePermission):
    """
    Grants access to Mobile App endpoints for both Observers and Admins.
    Logic:
    - ALLOW if: Within 5-day trial OR has an Active Pro plan.
    - BLOCK if: Trial expired AND no Pro plan active.
    """
    message = TRIAL_EXPIRED_RESPONSE

    def has_permission(self, request, view):
        sub = _get_sub(request.user)

        if not sub:
            self.message = NO_SUBSCRIPTION_RESPONSE
            return False

        # is_fully_active checks (is_trial_active OR is_pro_active)
        if sub.is_fully_active:
            return True

        self.message = TRIAL_EXPIRED_RESPONSE
        return False

# ══════════════════════════════════════════════════════════════════════
# 2. IsDashboardUser (Permission Class)
# ══════════════════════════════════════════════════════════════════════

class IsDashboardUser(BasePermission):
    """
    Restricts Dashboard endpoints to authorized Admins only.
    Logic:
    - BLOCK if: User is an Observer (regardless of payment status).
    - ALLOW if: User is Admin AND (Within trial OR Pro active).
    """
    message = DASHBOARD_FORBIDDEN

    def has_permission(self, request, view):
        user = request.user

        # STRICT RULE: Observers are never allowed in the Dashboard
        if not _is_admin(user):
            self.message = DASHBOARD_FORBIDDEN
            return False

        sub = _get_sub(user)
        if not sub:
            self.message = NO_SUBSCRIPTION_RESPONSE
            return False

        # Admins must also have an active subscription status
        if sub.is_fully_active:
            return True

        self.message = TRIAL_EXPIRED_RESPONSE
        return False

# ══════════════════════════════════════════════════════════════════════
# 3. TrialExpiryMiddleware (Global Guard)
# ══════════════════════════════════════════════════════════════════════

class TrialExpiryMiddleware:
    """
    Middleware to globally intercept protected API calls.
    If the trial has expired and no payment is found, it returns a 403.
    """

    # URLs that require an active trial/subscription
    PROTECTED_PATHS = (
        "/api/v1/observations/observations/",
        "/api/v1/observations/teachers/",
        "/api/v1/observations/analytics/",
        "/api/v1/accounts/profile/",
    )

    # URLs that remain accessible even after trial expiry
    SAFE_PATHS = (
        "/api/v1/auth/",
        "/api/v1/payments/",
        "/api/v1/community/",
        "/admin/",
        "/media/",
        "/static/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Step 1: Skip check for safe/public paths
        if any(path.startswith(s) for s in self.SAFE_PATHS):
            return self.get_response(request)

        # Step 2: Enforce check for protected/private paths
        if any(path.startswith(p) for p in self.PROTECTED_PATHS):
            user = getattr(request, 'user', None)
            
            if user and user.is_authenticated:
                # We mainly enforce this strictly for Observers/Regular users
                if not user.is_staff:
                    sub = _get_sub(user)
                    if sub and sub.is_trial_expired:
                        return JsonResponse(TRIAL_EXPIRED_RESPONSE, status=403)

        return self.get_response(request)

# ══════════════════════════════════════════════════════════════════════
# 4. Helper for Views
# ══════════════════════════════════════════════════════════════════════

def _has_active_access(user):
    """
    Checks if the user has an active subscription or is within trial.
    Used by views to guard specific actions.
    """
    sub = _get_sub(user)
    return bool(sub and sub.is_fully_active)