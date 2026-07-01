# """
# apps/payments/revenuecat_service.py
# ════════════════════════════════════
# WalkthroughPro-এর জন্য RevenueCat handler।
# আপনার existing Subscription model ব্যবহার করে — আলাদা plan/purchase model লাগে না।
# """

# import logging
# from datetime import datetime, timezone as dt_timezone
# from typing import Optional, Dict, Any

# from django.conf import settings
# from django.contrib.auth import get_user_model

# from .models import Subscription

# logger = logging.getLogger(__name__)
# User   = get_user_model()


# def _ms_to_datetime(ms) -> Optional[datetime]:
#     """RevenueCat millisecond timestamp → datetime"""
#     if ms is None:
#         return None
#     try:
#         return datetime.fromtimestamp(int(ms) / 1000, tz=dt_timezone.utc)
#     except (ValueError, TypeError):
#         return None


# class RevenueCatService:

#     PURCHASE_EVENTS = {
#         "INITIAL_PURCHASE",
#         "RENEWAL",
#         "PRODUCT_CHANGE",
#         "UNCANCELLATION",
#         "NON_RENEWING_PURCHASE",
#     }
#     CANCELLATION_EVENTS  = {"CANCELLATION"}
#     EXPIRATION_EVENTS    = {"EXPIRATION"}
#     BILLING_ISSUE_EVENTS = {"BILLING_ISSUE"}

#     def __init__(self):
#         self.secret_key = getattr(settings, 'REVENUECAT_SECRET_KEY', '')
#         if not self.secret_key:
#             logger.warning("REVENUECAT_SECRET_KEY not configured")

#     def _extract_app_user_id(self, data: Dict[str, Any]) -> Optional[str]:
#         """app_user_id সাধারণত event{} এর ভেতরে থাকে।"""
#         event = data.get("event", {})
#         app_user_id = event.get("app_user_id")
#         if app_user_id:
#             return app_user_id
#         customer = data.get("customer", {})
#         return customer.get("app_user_id")

#     def _get_user(self, app_user_id: str):
#         # ১. Django pk দিয়ে try (normal case)
#         try:
#             return User.objects.get(pk=app_user_id)
#         except (User.DoesNotExist, ValueError):
#             pass

#         # ২. Email দিয়ে try (fallback)
#         try:
#             return User.objects.get(email=app_user_id)
#         except User.DoesNotExist:
#             pass

#         # ৩. Anonymous ID — logIn() হয়নি
#         logger.error(
#             "RevenueCat: user not found for app_user_id='%s'. "
#             "App developer must call Purchases.logIn(djangoUserId) after login.",
#             app_user_id,
#         )
#         return None

#     def handle_webhook(self, event_type: str, data: Dict[str, Any]) -> None:
#         try:
#             app_user_id = self._extract_app_user_id(data)
#             if not app_user_id:
#                 logger.warning("RevenueCat: no app_user_id in webhook")
#                 return

#             user = self._get_user(app_user_id)
#             if not user:
#                 logger.warning("RevenueCat: user not found pk=%s", app_user_id)
#                 return

#             logger.info("RevenueCat webhook: user=%s event=%s", user.email, event_type)

#             if event_type in self.PURCHASE_EVENTS:
#                 self._handle_purchase(user, data)
#             elif event_type in self.CANCELLATION_EVENTS:
#                 self._handle_cancellation(user, data)
#             elif event_type in self.EXPIRATION_EVENTS:
#                 self._handle_expiration(user, data)
#             elif event_type in self.BILLING_ISSUE_EVENTS:
#                 logger.warning("RevenueCat billing issue: user=%s", user.email)
#             else:
#                 logger.info("RevenueCat: unhandled event — %s", event_type)

#         except Exception as exc:
#             logger.error("RevenueCat dispatch error: %s", exc, exc_info=True)

#     def _get_event_field(self, data: Dict[str, Any], key: str):
#         return data.get("event", {}).get(key)

#     def _handle_purchase(self, user, data: Dict[str, Any]) -> None:
#         """Purchase / renewal → Pro activate"""
#         product_id    = self._get_event_field(data, "product_id")
#         expiration_ms = self._get_event_field(data, "expiration_at_ms")
#         expiry_dt     = _ms_to_datetime(expiration_ms)

#         sub, _ = Subscription.objects.get_or_create(user=user)
#         sub.plan_type = 'professional'
#         sub.status    = 'active'
#         sub.revenuecat_app_user_id = str(user.pk)
#         if expiry_dt:
#             sub.pro_end_date = expiry_dt
#         sub.save()

#         logger.info(
#             "✅ RevenueCat: Pro activated — user=%s product=%s expiry=%s",
#             user.email, product_id, expiry_dt,
#         )

#     def _handle_cancellation(self, user, data: Dict[str, Any]) -> None:
#         """Cancel করলেও expiry পর্যন্ত access থাকে — শুধু log রাখি।"""
#         logger.info("RevenueCat: Cancelled (access until expiry) — user=%s", user.email)

#     def _handle_expiration(self, user, data: Dict[str, Any]) -> None:
#         """Subscription পুরোপুরি শেষ → expired করি।"""
#         try:
#             sub = user.subscription
#             sub.status = 'expired'
#             sub.save(update_fields=['status', 'updated_at'])
#             logger.info("RevenueCat: Expired — user=%s", user.email)
#         except Subscription.DoesNotExist:
#             logger.warning("RevenueCat: no subscription to expire — user=%s", user.email)


# revenuecat = RevenueCatService()





"""
WalkthroughPro-এর জন্য RevenueCat handler।
আপনার existing Subscription model ব্যবহার করে — আলাদা plan/purchase model লাগে না।
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Subscription

logger = logging.getLogger(__name__)
User = get_user_model()


def _ms_to_datetime(ms) -> Optional[datetime]:
    """RevenueCat millisecond timestamp → datetime (Timezone Aware)"""
    if ms is None:
        return None
    try:
        # জ্যাঙ্গোর কারেন্ট টাইমজোন ব্যবহার করে ডেট অবজেক্ট বানালে Timezone Offset Conflict হবে না
        return timezone.datetime.fromtimestamp(int(ms) / 1000, tz=timezone.get_current_timezone())
    except (ValueError, TypeError):
        return None


class RevenueCatService:

    PURCHASE_EVENTS = {
        "INITIAL_PURCHASE",
        "RENEWAL",
        "PRODUCT_CHANGE",
        "UNCANCELLATION",
        "NON_RENEWING_PURCHASE",
    }
    CANCELLATION_EVENTS  = {"CANCELLATION"}
    EXPIRATION_EVENTS    = {"EXPIRATION"}
    BILLING_ISSUE_EVENTS = {"BILLING_ISSUE"}

    def __init__(self):
        self.secret_key = getattr(settings, 'REVENUECAT_SECRET_KEY', '')
        if not self.secret_key:
            logger.warning("REVENUECAT_SECRET_KEY not configured")

    def _extract_app_user_id(self, data: Dict[str, Any]) -> Optional[str]:
        """app_user_id সাধারণত event{} এর ভেতরে থাকে।"""
        event = data.get("event", {})
        app_user_id = event.get("app_user_id")
        if app_user_id:
            return app_user_id
        customer = data.get("customer", {})
        return customer.get("app_user_id")

    def _get_user(self, app_user_id: str):
        # ১. Django pk দিয়ে try (normal case)
        try:
            return User.objects.get(pk=app_user_id)
        except (User.DoesNotExist, ValueError):
            pass

        # ২. Email দিয়ে try (fallback)
        try:
            return User.objects.get(email=app_user_id)
        except User.DoesNotExist:
            pass

        # ৩. Anonymous ID — logIn() হয়নি
        logger.error(
            "RevenueCat: user not found for app_user_id='%s'. "
            "App developer must call Purchases.logIn(djangoUserId) after login.",
            app_user_id,
        )
        return None

    def handle_webhook(self, event_type: str, data: Dict[str, Any]) -> None:
        try:
            app_user_id = self._extract_app_user_id(data)
            if not app_user_id:
                logger.warning("RevenueCat: no app_user_id in webhook")
                return

            user = self._get_user(app_user_id)
            if not user:
                logger.warning("RevenueCat: user not found pk=%s", app_user_id)
                return

            logger.info("RevenueCat webhook: user=%s event=%s", user.email, event_type)

            if event_type in self.PURCHASE_EVENTS:
                self._handle_purchase(user, data)
            elif event_type in self.CANCELLATION_EVENTS:
                self._handle_cancellation(user, data)
            elif event_type in self.EXPIRATION_EVENTS:
                self._handle_expiration(user, data)
            elif event_type in self.BILLING_ISSUE_EVENTS:
                logger.warning("RevenueCat billing issue: user=%s", user.email)
            else:
                logger.info("RevenueCat: unhandled event — %s", event_type)

        except Exception as exc:
            logger.error("RevenueCat dispatch error: %s", exc, exc_info=True)

    def _get_event_field(self, data: Dict[str, Any], key: str):
        return data.get("event", {}).get(key)

    def _handle_purchase(self, user, data: Dict[str, Any]) -> None:
        """Purchase / renewal → Pro activate"""
        product_id    = self._get_event_field(data, "product_id")
        expiration_ms = self._get_event_field(data, "expiration_at_ms")
        expiry_dt     = _ms_to_datetime(expiration_ms)

        sub, _ = Subscription.objects.get_or_create(user=user)
        sub.plan_type = 'professional'
        sub.status    = 'active'
        sub.revenuecat_app_user_id = str(user.pk)
        if expiry_dt:
            sub.pro_end_date = expiry_dt
        sub.save()

        logger.info(
            "✅ RevenueCat: Pro activated — user=%s product=%s expiry=%s",
            user.email, product_id, expiry_dt,
        )

    def _handle_cancellation(self, user, data: Dict[str, Any]) -> None:
        """Cancel করলেও expiry পর্যন্ত access থাকে — শুধু log রাখি।"""
        logger.info("RevenueCat: Cancelled (access until expiry) — user=%s", user.email)

    def _handle_expiration(self, user, data: Dict[str, Any]) -> None:
        """Subscription পুরোপুরি শেষ → expired করি।"""
        try:
            sub = user.subscription
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            logger.info("RevenueCat: Expired — user=%s", user.email)
        except Subscription.DoesNotExist:
            logger.warning("RevenueCat: no subscription to expire — user=%s", user.email)


revenuecat = RevenueCatService()