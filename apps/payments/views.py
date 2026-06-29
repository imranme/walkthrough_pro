"""
apps/payments/views.py
Web: Stripe payment + 5-day Trial Flow
Mobile: SubscriptionStatusView + RevenueCat Webhook Integration
"""

import json
import logging
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import datetime

from .models import Invoice, Subscription
from .serializers import InvoiceSerializer
from .permissions import _is_mobile_request

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)
User = get_user_model()


# ══════════════════════════════════════════════════════════════════════
# 1. Start Trial (Web only)
# ══════════════════════════════════════════════════════════════════════

class StartTrialView(APIView):
    """
    POST /api/v1/payments/start-trial/
    Web: "Start Free Trial" button
    Mobile: RevenueCat handles trial — এই endpoint call করবে না
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        # Staff/Superuser → no trial needed (সুপার অ্যাডমিন আজীবন ফ্রি)
        if user.is_staff or user.is_superuser:
            return Response({"message": "Staff access. No trial needed."})

        sub, created = Subscription.objects.get_or_create(user=user)

        if not created:
            if sub.plan_type == 'professional' and sub.status == 'active':
                return Response({"error": "Already have active Pro plan."}, status=400)
            if sub.is_trial_active:
                return Response({
                    "message":        "Trial already running.",
                    "days_remaining": sub.trial_days_remaining,
                    "trial_end_date": sub.trial_end_date,
                })
            if not sub.is_trial_active:
                return Response({
                    "error":   "trial_expired",
                    "message": "Trial expired. Please upgrade to Pro.",
                    "upgrade_url": "https://walkthroughpro.app/pricing",
                }, status=400)

        sub.plan_type        = 'free_trial'
        sub.status           = 'trial'
        sub.trial_start_date = timezone.now()
        sub.trial_end_date   = timezone.now() + timedelta(days=5)
        sub.save()

        return Response({
            "message":        "5-day free trial started!",
            "trial_end_date": sub.trial_end_date,
            "days_remaining": sub.trial_days_remaining,
        }, status=201)


# ══════════════════════════════════════════════════════════════════════
# 2. Subscription Status
# Web: Django subscription check
# Mobile: RevenueCat-এর জন্য শুধু user info দেয়
# ══════════════════════════════════════════════════════════════════════

class SubscriptionStatusView(APIView):
    """
    GET /api/v1/payments/subscription/

    Web frontend: Uses is_fully_active, days_left, and can_purchase
    Mobile app: Bypasses RevenueCat if is_staff/superuser
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Superuser/Staff → always active, no payment needed
        if user.is_staff or user.is_superuser:
            return Response(
                {
                    "plan_type": "staff",
                    "status": "active",
                    "is_fully_active": True,
                    "is_staff": True,
                    "days_left": 9999,
                    "can_purchase": False,
                    "trial_days_remaining": 0,
                    "upgrade_url": None,
                }
            )

        # Mobile → RevenueCat handles subscription
        if _is_mobile_request(request):
            return Response(
                {
                    "is_staff": False,
                    "is_superuser": False,
                    "revenuecat_user_id": str(user.pk),
                    "email": user.email,
                    "mobile_access": "managed_by_revenuecat",
                }
            )

        # Web → Django subscription check
        try:
            sub = user.subscription
        except Exception:
            return Response(
                {
                    "plan_type": "free",
                    "status": "no_subscription",
                    "is_fully_active": False,
                    "days_left": 0,
                    "can_purchase": True,
                    "upgrade_url": "https://walkthroughpro.app/pricing",
                }
            )

        # Calculate remaining subscription days dynamically
        # Calculate remaining subscription days dynamically
        days_left = 0
if sub.is_fully_active:
    if sub.is_trial_active and sub.trial_end_date:
        delta = sub.trial_end_date - timezone.now()
        days_left = max(0, delta.days)

    elif sub.is_pro_active:
        # pro_end_date আছে কিনা দেখো
        if sub.pro_end_date and sub.pro_end_date > timezone.now():
            delta = sub.pro_end_date - timezone.now()
            days_left = max(0, delta.days)
        else:
            # pro_end_date নেই → Stripe থেকে আনো
            try:
                if sub.stripe_subscription_id:
                    stripe_sub = stripe.Subscription.retrieve(
                        sub.stripe_subscription_id
                    )
                    import datetime
                    end_ts  = stripe_sub.current_period_end
                    end_dt  = datetime.datetime.fromtimestamp(end_ts, tz=timezone.utc)
                    # DB-তে save করো future calls-এর জন্য
                    sub.pro_end_date = end_dt
                    sub.save(update_fields=['pro_end_date'])
                    delta    = end_dt - timezone.now()
                    days_left = max(0, delta.days)
                else:
                    days_left = 30  # fallback
            except Exception:
                days_left = 30  # fallback

        # Determine if the frontend should block/allow new checkouts
        can_purchase = not sub.is_fully_active

        return Response(
            {
                "plan_type": sub.plan_type,
                "status": sub.status,
                "is_fully_active": sub.is_fully_active,
                "is_trial_active": sub.is_trial_active,
                "is_pro_active": sub.is_pro_active,
                "trial_days_remaining": sub.trial_days_remaining,
                "trial_end_date": sub.trial_end_date,
                "days_left": days_left,
                "can_purchase": can_purchase,
                "upgrade_url": (
                    None
                    if sub.is_fully_active
                    else "https://walkthroughpro.app/pricing"
                ),
            }
        )

# ══════════════════════════════════════════════════════════════════════
# 3. Stripe Checkout (Web)
# ══════════════════════════════════════════════════════════════════════

class CreateCheckoutSessionView(APIView):
    """
    POST /api/v1/payments/create-checkout-session/
    Web only — Mobile uses RevenueCat In-App Purchase
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            # 1. Extract price_id or plan_type from request body
            received_price_id = request.data.get('price_id')
            requested_plan = request.data.get('plan_type', '').lower()

            # 2. Assign the target price ID dynamically
            if received_price_id:
                target_price_id = received_price_id
            elif requested_plan == 'yearly':
                target_price_id = settings.STRIPE_YEARLY_PRICE_ID
            else:
                target_price_id = settings.STRIPE_PRO_PRICE_ID

            # 3. Customer ID management logic
            sub         = getattr(user, 'subscription', None)
            customer_id = sub.stripe_customer_id if sub else None

            if not customer_id:
                customer    = stripe.Customer.create(
                    email    = user.email,
                    name     = user.get_full_name() or user.username,
                    metadata = {"django_user_id": str(user.pk)},
                )
                customer_id = customer.id
                if sub:
                    sub.stripe_customer_id = customer_id
                    sub.save(update_fields=['stripe_customer_id'])

            # 4. Create Stripe checkout session using the target_price_id
            session = stripe.checkout.Session.create(
                customer             = customer_id,
                payment_method_types = ['card'],
                line_items           = [{'price': target_price_id, 'quantity': 1}],
                mode                 = 'subscription',
                success_url          = f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url           = f"{settings.FRONTEND_URL}/pricing?cancelled=true",
                client_reference_id  = str(user.pk),
                metadata             = {'user_id': str(user.pk)},
                allow_promotion_codes = True,
            )
            return Response({"url": session.url, "session_id": session.id})

        except stripe.error.StripeError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.error("Checkout session error: %s", exc)
            return Response({"error": "Internal error"}, status=500)
# ══════════════════════════════════════════════════════════════════════
# 4. Verify Payment
# ══════════════════════════════════════════════════════════════════════

class VerifyPaymentView(APIView):
    """POST /api/v1/payments/verify/ — success page এ call করুন"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({"error": "session_id required"}, status=400)
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                return Response({"status": "success", "message": "Payment verified."})
            return Response({"status": "pending"}, status=202)
        except stripe.error.StripeError as exc:
            return Response({"error": str(exc)}, status=400)



# ══════════════════════════════════════════════════════════════════════
# 8. Cancel Subscription (Web/Stripe)
# ══════════════════════════════════════════════════════════════════════

class CancelSubscriptionView(APIView):
    """
    POST /api/v1/payments/cancel-subscription/
    ইউজারের একটিভ স্ট্রাইপ সাবস্ক্রিপশন ক্যানসেল বা অটো-রিনিউ অফ করার জন্য।
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            sub = getattr(user, 'subscription', None)
            if not sub or not sub.stripe_subscription_id:
                return Response({"error": "No active Stripe subscription found."}, status=400)

            # স্ট্রাইপ ক্লাউড থেকে সাবস্ক্রিপশনটি পিরিয়ডের শেষে ক্যানসেল করার রিকোয়েস্ট
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True
            )

            sub.status = 'cancelled'
            sub.save(update_fields=['status'])
            
            logger.info("Stripe subscription set to cancel at period end for user: %s", user.email)
            return Response({"message": "Subscription will be cancelled at the end of the billing period."})

        except stripe.error.StripeError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.error("Cancel subscription error: %s", exc)
            return Response({"error": "Internal server error"}, status=500)

# ══════════════════════════════════════════════════════════════════════
# 5. Invoice List
# ══════════════════════════════════════════════════════════════════════

class InvoiceListView(APIView):
    """
    GET /api/v1/payments/invoices/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            # 1. Safe extraction of subscription object
            sub = getattr(user, "subscription", None)
            if not sub:
                return Response(
                    {"message": "No subscription record found for this user."},
                    status=status.HTTP_200_OK,
                )

            # 2. Dynamic check for customer ID fields (matches your exact model attribute)
            customer_id = (
                getattr(sub, "stripe_customer_id", None)
                or getattr(sub, "customer_id", None)
                or getattr(sub, "stripe_id", None)
            )

            # If no stripe customer reference is found in DB, return empty list gracefully
            if not customer_id:
                return Response(
                    {"message": "No Stripe customer ID linked to this profile."},
                    status=status.HTTP_200_OK,
                )

            # 3. Fetch from Stripe
            invoices = stripe.Invoice.list(customer=customer_id, limit=10)

            invoice_data = []
            for inv in invoices.data:
                invoice_data.append(
                    {
                        "id": inv.id,
                        "number": inv.number,
                        "amount_paid": inv.amount_paid / 100,
                        "currency": inv.currency.upper(),
                        "status": inv.status,
                        "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None),
                        "invoice_pdf": getattr(inv, "invoice_pdf", None),
                        "created_at": datetime.fromtimestamp(inv.created).strftime(
                            "%Y-%m-%d"
                        ),
                    }
                )

            return Response(invoice_data, status=status.HTTP_200_OK)

        except stripe.error.StripeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            # 🎯 এটি আপনার পাইথন রানিং টার্মিনালে আসল এররটি প্রিন্ট করবে
            print("\n" + "=" * 50)
            print(f"🎯 ACTUAL INVOICE ERROR: {str(exc)}")
            print("=" * 50 + "\n")

            return Response(
                {
                    "error": "Internal server configuration error.",
                    "debug_message": str(exc),  # পোস্টম্যান ডেস্কেই এররটি দেখতে পাবেন
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# ══════════════════════════════════════════════════════════════════════
# 6. Stripe Webhook (Web Platform)
# ══════════════════════════════════════════════════════════════════════

@csrf_exempt
def stripe_webhook(request):
    """POST /api/v1/payments/webhook/"""
    payload    = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        logger.error("Webhook signature error: %s", exc)
        return HttpResponse(status=400)

    event_type = event['type']
    raw_data   = event['data']['object']

    if hasattr(raw_data, 'to_dict_deep'):
        data = raw_data.to_dict_deep()
    elif hasattr(raw_data, 'to_dict'):
        data = raw_data.to_dict()
    else:
        data = dict(raw_data)

    logger.info("Stripe Webhook received: %s", event_type)

    if event_type in ('checkout.session.completed', 'invoice.paid'):
        _activate_pro(data)
    elif event_type == 'customer.subscription.deleted':
        _deactivate_sub(data)

    return HttpResponse(status=200)


def _activate_pro(data: dict):
    user_id = (
        data.get('client_reference_id')
        or (data.get('metadata') or {}).get('user_id')
    )
    logger.info("_activate_pro: user_id=%s", user_id)

    if not user_id:
        logger.error("No user_id in webhook data")
        return

    try:
        user          = User.objects.get(pk=user_id)
        sub, _        = Subscription.objects.get_or_create(user=user)
        sub.plan_type = 'professional'
        sub.status    = 'active'
        sub.stripe_subscription_id = data.get('subscription')
        sub.stripe_customer_id     = data.get('customer')
        sub.pro_end_date           = timezone.now() + timedelta(days=30)
        sub.save()
        logger.info("Pro activated via Stripe: user=%s", user.email)
    except User.DoesNotExist:
        logger.error("User not found: pk=%s", user_id)
    except Exception as exc:
        logger.error("_activate_pro error: %s", exc)


def _deactivate_sub(data: dict):
    stripe_sub_id = data.get('id')
    try:
        sub        = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
        sub.status = 'expired'
        sub.save(update_fields=['status'])
        logger.info("Stripe Subscription expired: user=%s", sub.user_id)
    except Subscription.DoesNotExist:
        logger.warning("No subscription found for stripe_id=%s", stripe_sub_id)


# ══════════════════════════════════════════════════════════════════════
# 7. RevenueCat Webhook (Mobile App Platform)
# ══════════════════════════════════════════════════════════════════════

@csrf_exempt
def revenuecat_webhook(request):
    """
    POST /api/v1/payments/revenuecat-webhook/
    RevenueCat V2 Webhook API ইন্টিগ্রেশন। অ্যাপ স্টোর ও গুগল প্লে পেমেন্ট রিয়েল-টাইমে ক্যাচ করে।
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # সিকিউরিটি ভেরিফিকেশন: RevenueCat Header Token চেক
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if settings.REVENUECAT_WEBHOOK_SECRET and auth_header != f"Bearer {settings.REVENUECAT_WEBHOOK_SECRET}":
        logger.error("Unauthorized access attempt on RevenueCat webhook endpoint.")
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    event = payload.get('event', {})
    event_type = event.get('type')
    user_id = event.get('app_user_id')  # অ্যাপ থেকে পাস করা জ্যাঙ্গো User PK/ID

    logger.info("RevenueCat Webhook Triggered: %s for user_id=%s", event_type, user_id)

    if not user_id:
        return JsonResponse({"error": "app_user_id missing"}, status=400)

    try:
        user = User.objects.get(pk=user_id)
        sub, _ = Subscription.objects.get_or_create(user=user)

        # পেমেন্ট সাকসেসফুল অথবা সাবস্ক্রিপশন রিনিউ হলে
        if event_type in ('INITIAL_PURCHASE', 'RENEWAL', 'SUBSCRIBER_ALIAS'):
            sub.plan_type = 'professional'
            sub.status = 'active'
            
            # RevenueCat এর এক্সপায়ারি টাইমস্ট্যাম্পকে ডাটাবেজের ডিরেক্ট ডেটটাইমে কনভার্ট করা
            expires_at_ms = event.get('expiration_at_ms')
            if expires_at_ms:
                sub.pro_end_date = timezone.datetime.fromtimestamp(expires_at_ms / 1000.0, tz=timezone.utc)
            else:
                sub.pro_end_date = timezone.now() + timedelta(days=30) # সেফটি ব্যাকআপ ৩০ দিন
                
            sub.save()
            logger.info("Pro activated via Mobile RevenueCat: user=%s", user.email)

        # সাবস্ক্রিপশন টাইমআউট বা ইউজার রিফান্ড/ক্যান্সেল করলে 
        elif event_type in ('EXPIRATION', 'CANCELLATION'):
            sub.status = 'expired'
            sub.save(update_fields=['status'])
            logger.info("RevenueCat plan expired/cancelled for user=%s", user.email)

    except User.DoesNotExist:
        logger.error("RevenueCat webhook: Django User ID %s not found.", user_id)
    except Exception as exc:
        logger.error("RevenueCat webhook parsing error: %s", exc)
        return JsonResponse({"error": "Internal webhook processing error"}, status=500)

    return JsonResponse({"status": "success"}, status=200)