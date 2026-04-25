from rest_framework.permissions import BasePermission

class IsSubscriptionActive(BasePermission):
    """
    Grants access if the user has an active trial or a professional subscription.
    Blocks access (403) with an upgrade prompt if the trial has expired.
    
    Usage in views:
    permission_classes = [IsAuthenticated, IsSubscriptionActive]
    """

    def has_permission(self, request, view):
        # 1. Ensure user is logged in
        if not request.user or not request.user.is_authenticated:
            return False

        # 2. Try to get the subscription object
        try:
            sub = request.user.subscription
        except Exception:
            self.message = {
                "error":   "no_subscription",
                "message": "No active subscription found. Please start your trial.",
            }
            return False

        # 3. Check access using the model property logic
        if sub.is_active:
            return True

        # 4. Handle expired trial/inactive status
        self.message = {
            "error":       "trial_expired",
            "message":     "Your 5-day trial is over. Please upgrade to Pro to continue.",
            "upgrade_url": "https://walkthroughpro.com/pricing",
        }
        return False