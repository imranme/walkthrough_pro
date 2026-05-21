from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

# ══════════════════════════════════════════════════════════════════════
# 🎯 কাস্টম এরর রেসপন্স (Custom Error Responses)
# ══════════════════════════════════════════════════════════════════════

# মোবাইল অ্যাপের জন্য: এটি পাওয়া মাত্রই অ্যাপ টোকেন ডিলিট করে লগআউট করাবে
APP_TRIAL_EXPIRED_RESPONSE = {
    "error": "token_invalidated_trial_expired",
    "message": "Your 5-day trial has expired. Please upgrade to a Professional plan to continue.",
    "action": "FORCE_LOGOUT",
    "upgrade_url": "https://walkthroughpro.app/pricing"
}

# ওয়েবসাইটের জন্য: লগইন থাকবে, কিন্তু প্রিমিয়াম ডাটা লক থাকবে
WEB_TRIAL_EXPIRED_RESPONSE = {
    "error": "trial_expired",
    "message": "Your 5-day trial has expired. Access to premium tools/dashboard is locked. Please make a payment.",
    "action": "SHOW_PAYMENT_WALL",
    "upgrade_url": "https://walkthroughpro.app/pricing"
}

DASHBOARD_FORBIDDEN = {
    "error": "access_denied",
    "message": "Access Denied: The Analytics Dashboard is reserved for Admin users and strictly restricted for Observers.",
}

# ══════════════════════════════════════════════════════════════════════
# 🔍 ইন্টারনাল হেল্পার ফাংশন
# ══════════════════════════════════════════════════════════════════════
def _get_sub(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.subscription
    except Exception:
        return None

def _is_mobile_request(request):
    """অনুরোধটি মোবাইল অ্যাপ থেকে এসেছে নাকি ওয়েবসাইট থেকে, তা চেক করার মেথড।"""
    return request.headers.get('X-Client-Type') == 'mobile' or 'HTTP_X_CLIENT_TYPE' in request.META


# ══════════════════════════════════════════════════════════════════════
# 🛡️ ১. IsAppUser (মোবাইল অ্যাপ এবং সাধারণ ফিচারের জন্য গেট)
# ══════════════════════════════════════════════════════════════════════
class IsAppUser(BasePermission):
    """
    টিচার লিস্ট, রিপোর্ট জেনারেট এবং অবসারভেশন এপিআই প্রটেক্ট করার জন্য।
    ৫ দিনের ট্রায়াল শেষ হলে মোবাইল ইউজারকে ফোর্স লগআউট করবে।
    """
    def has_permission(self, request, view):
        user = request.user
        
        # শর্ত ১: সুপার অ্যাডমিন সবসময় সম্পূর্ণ ফ্রি পাস
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return True 

        sub = _get_sub(user)
        if not sub:
            raise PermissionDenied(detail={"error": "no_subscription", "message": "No active subscription found."})
        
        # যদি ৫ দিনের ট্রায়াল বা প্রো একটিভ থাকে, তবে অ্যাক্সেস পাবে
        if sub.has_app_access:
            return True
            
        # ট্রায়াল শেষ হয়ে গেলে ডিভাইস অনুযায়ী এক্সপায়ার্ড এরর থ্রো করা
        if _is_mobile_request(request):
            raise PermissionDenied(detail=APP_TRIAL_EXPIRED_RESPONSE)
        else:
            raise PermissionDenied(detail=WEB_TRIAL_EXPIRED_RESPONSE)


# ══════════════════════════════════════════════════════════════════════
# 📊 ২. IsDashboardUser (ওয়েব ড্যাশবোর্ড / অ্যানালিটিক্স গেট)
# ══════════════════════════════════════════════════════════════════════
class IsDashboardUser(BasePermission):
    """
    শুধুমাত্র এডমিনদের ড্যাশবোর্ড ডেটা দেখানোর জন্য।
    অবজারভারদের আজীবন ব্লক করবে এবং ট্রায়াল শেষ হলে এডমিনদের পেমেন্ট ওয়াল দেখাবে।
    """
    def has_permission(self, request, view):
        user = request.user
        
        # সুপার অ্যাডমিন সবসময় ফ্রি অ্যাক্সেস পাবে
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return True

        # শর্ত ২: ইউজার অবজারভার হলে ট্রায়াল থাকলেও ড্যাশবোর্ড আজীবন লক (লগআউট হবে না, শুধু এপিআই ব্লক)
        if hasattr(user, 'profile') and getattr(user.profile, 'is_observer', False):
            raise PermissionDenied(detail=DASHBOARD_FORBIDDEN)

        # শর্ত ৩: সাধারণ অ্যাডমিনদের জন্য ট্রায়াল ভ্যালিডিটি চেক
        sub = _get_sub(user)
        if sub and sub.has_app_access:
            return True
            
        # অ্যাডমিনের ৫ দিন শেষ হয়ে গেলে ড্যাশবোর্ড লক করে পেমেন্ট ওয়াল দেখাবে (লগআউট করাবে না)
        raise PermissionDenied(detail=WEB_TRIAL_EXPIRED_RESPONSE)