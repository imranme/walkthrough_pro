import logging
import stripe
import math
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Invoice, Subscription
from .serializers import InvoiceSerializer
from .permissions import _is_mobile_request, _get_sub

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)
User = get_user_model()


class StartTrialView(APIView):
    """
    POST /api/v1/payments/start-trial/
    Web: "Start Free Trial" button
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_staff or user.is_superuser:
            return Response({"message": "Staff access. No trial needed."})

        sub, created = Subscription.objects.get_or_create(user=user)

        if not created:
            if sub.plan_type == 'professional' and sub.status == 'active':
                return Response({"error": "Already have active Pro plan."}, status=400)
            if getattr(sub, 'is_trial_active', False):
                return Response({
                    "message":        "Trial already running.",
                    "days_remaining": getattr(sub, 'trial_days_remaining', 5),
                    "trial_end_date": sub.trial_end_date,
                })
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
            "days_remaining": getattr(sub, 'trial_days_remaining', 5),
        }, status=201)


class SubscriptionStatusView(APIView):
    """
    GET /api/v1/payments/subscription/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.is_staff or user.is_superuser:
            return Response({
                "plan_type":        "staff",
                "status":           "active",
                "is_fully_active":  True,
                "is_staff":         True,
                "trial_days_remaining": 0,
                "upgrade_url":      None,
            })

        if _is_mobile_request(request):
            return Response({
                "is_staff":        False,
                "is_superuser":    False,
                "revenuecat_user_id": str(user.pk),
                "email":           user.email,
                "mobile_access":   "managed_by_revenuecat",
            })

        sub = _get_sub(user)
        if not sub:
            return Response({
                "plan_type":       None,
                "status":          "no_subscription",
                "is_fully_active": False,
                "upgrade_url":     "https://walkthroughpro.app/pricing",
            })

        active_access = getattr(sub, 'is_fully_active', False)

        # ─── DYNAMIC DAYS REMAINING CALCULATOR BASED ON ACTIVE PLAN ───
        now = timezone.now()
        days_remaining = 0

        if sub.plan_type == 'professional' and sub.status == 'active':
            # Calculate remaining days for professional plan (Monthly or Yearly)
            if getattr(sub, 'pro_end_date', None) and sub.pro_end_date > now:
                days_remaining = math.ceil((sub.pro_end_date - now).total_seconds() / 86400)
        else:
            # Fallback to trial remaining days if not professional
            if getattr(sub, 'trial_end_date', None) and sub.trial_end_date > now:
                days_remaining = math.ceil((sub.trial_end_date - now).total_seconds() / 86400)

        return Response({
            "plan_type":            sub.plan_type,
            "status":               sub.status,
            "is_fully_active":      active_access,
            "is_trial_active":      True if sub.plan_type == 'free_trial' and sub.status == 'trial' else False,
            "is_pro_active":        True if sub.plan_type == 'professional' and sub.status == 'active' else False,
            "trial_days_remaining": days_remaining, # Returns 30 or 365 dynamically based on current active plan
            "trial_end_date":       sub.pro_end_date if sub.plan_type == 'professional' else sub.trial_end_date,
            "upgrade_url":          None if active_access else "https://walkthroughpro.app/pricing",
        })


class CreateCheckoutSessionView(APIView):
    """
    POST /api/v1/payments/create-checkout-session/
    Body parameters: {"plan_type": "monthly"} OR {"plan_type": "yearly"}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        requested_plan = request.data.get('plan_type', 'monthly').lower()
        
        if requested_plan == 'yearly':
            price_id = getattr(settings, 'STRIPE_YEARLY_PRICE_ID', None)
            if not price_id:
                return Response({"error": "Yearly price ID is not configured in settings."}, status=400)
        else:
            price_id = settings.STRIPE_PRO_PRICE_ID

        try:
            sub         = _get_sub(user)
            customer_id = sub.stripe_customer_id if sub else None

            if not customer_id:
                customer = stripe.Customer.create(
                    email    = user.email,
                    name     = user.get_full_name() or user.username,
                    metadata = {"django_user_id": str(user.pk)},
                )
                customer_id = customer.id
                if sub:
                    sub.stripe_customer_id = customer_id
                    sub.save(update_fields=['stripe_customer_id'])

            session = stripe.checkout.Session.create(
                customer             = customer_id,
                payment_method_types = ['card'],
                line_items           = [{'price': price_id, 'quantity': 1}],
                mode                 = 'subscription',
                success_url          = f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url           = f"{settings.FRONTEND_URL}/pricing?cancelled=true",
                client_reference_id  = str(user.pk),
                metadata             = {
                    'user_id': str(user.pk),
                    'plan_interval': 'year' if requested_plan == 'yearly' else 'month'
                },
                allow_promotion_codes = True,
            )
            return Response({"url": session.url, "session_id": session.id})
        except stripe.error.StripeError as exc:
            return Response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.error("Checkout session error: %s", exc)
            return Response({"error": "Internal error"}, status=500)


class VerifyPaymentView(APIView):
    """
    POST /api/v1/payments/verify/
    """
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


class CancelSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        sub = _get_sub(user)
        if sub and sub.stripe_subscription_id:
            try:
                stripe.Subscription.delete(sub.stripe_subscription_id)
                sub.status = 'cancelled'
                sub.save(update_fields=['status'])
                return Response({"message": "Subscription cancelled successfully."})
            except stripe.error.StripeError as exc:
                return Response({"error": str(exc)}, status=400)
        return Response({"error": "No active Stripe subscription found."}, status=400)


class InvoiceListView(generics.ListAPIView):
    serializer_class   = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user).order_by('-invoice_date')


# ══════════════════════════════════════════════════════════════════════
# 💳 STRIPE WEBHOOK HANDLING (Supports Monthly / Yearly Splits)
# ══════════════════════════════════════════════════════════════════════

# @csrf_exempt
# def stripe_webhook(request):
#     payload    = request.body
    
#     # ─── 🧪 FOR POSTMAN TESTING (Bypass Signature) ───
#     import json
#     raw_data = json.loads(payload)
#     event_type = raw_data.get('type')
#     data = raw_data.get('data', {}).get('object', {})
#     # ─────────────────────────────────────────────────

#     # Comment out the actual Stripe verification block during Postman testing
#     """
#     sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
#         )
#     except Exception as exc:
#         logger.error("Webhook signature verification failed: %s", exc)
#         return HttpResponse(status=400)

#     event_type = event['type']
#     raw_data   = event['data']['object']
#     """

#     # The rest of your code handles 'data' smoothly
#     if hasattr(raw_data, 'to_dict_deep'):
#         data = raw_data.to_dict_deep()
#     elif hasattr(raw_data, 'to_dict'):
#         data = raw_data.to_dict()
#     else:
#         data = dict(raw_data)

#     logger.info("Webhook processed via Postman: %s", event_type)

#     if event_type in ('checkout.session.completed', 'invoice.paid'):
#         _activate_pro(data)
#     elif event_type == 'customer.subscription.deleted':
#         _deactivate_sub(data)

#     return HttpResponse(status=200)

#live test:

@csrf_exempt
def stripe_webhook(request):
    """
    Production-ready Stripe Webhook handler with signature verification.
    Handles 'checkout.session.completed', 'invoice.paid', and 'customer.subscription.deleted'.
    """
    payload    = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        # Verify webhook signature using Stripe secret key
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        logger.error("Webhook signature verification failed: %s", exc)
        return HttpResponse(status=400)

    event_type = event['type']
    raw_data   = event['data']['object']
    
    # Safely convert Stripe object data into a deep dictionary context
    if hasattr(raw_data, 'to_dict_deep'):
        data = raw_data.to_dict_deep()
    elif hasattr(raw_data, 'to_dict'):
        data = raw_data.to_dict()
    else:
        data = dict(raw_data)

    logger.info("Stripe Webhook processed successfully: %s", event_type)

    # Route events to corresponding subscription business logic
    if event_type in ('checkout.session.completed', 'invoice.paid'):
        _activate_pro(data)
    elif event_type == 'customer.subscription.deleted':
        _deactivate_sub(data)

    return HttpResponse(status=200)


def _activate_pro(data: dict):
    user_id = data.get('client_reference_id') or (data.get('metadata') or {}).get('user_id')
    
    if not user_id and data.get('customer'):
        try:
            customer = stripe.Customer.retrieve(data.get('customer'))
            user_id = customer.metadata.get('django_user_id')
        except Exception:
            pass

    logger.info("_activate_pro: user_id=%s", user_id)
    if not user_id:
        logger.error("No user_id found in webhook data context.")
        return

    try:
        user          = User.objects.get(pk=user_id)
        sub, _        = Subscription.objects.get_or_create(user=user)
        sub.plan_type = 'professional'
        sub.status    = 'active'
        
        stripe_sub = data.get('subscription')
        if not stripe_sub and data.get('object') == 'subscription':
            stripe_sub = data.get('id')
            
        sub.stripe_subscription_id = stripe_sub
        sub.stripe_customer_id     = data.get('customer')

        # ─── DETERMINE DAYS TO ADD BASED ON PLAN INTERVAL ───
        days_to_add = 30  
        
        # Check metadata interval (For checkout session objects)
        metadata_interval = (data.get('metadata') or {}).get('plan_interval')
        
        # Check line item interval (For invoice objects)
        lines = data.get('lines', {}).get('data', [])
        line_interval = lines.get('plan', {}).get('interval', '') if lines else ''
        
        if metadata_interval == 'year' or line_interval == 'year':
            days_to_add = 365

        sub.pro_end_date = timezone.now() + timedelta(days=days_to_add)
        sub.save()
        
        # Create tracking history invoice
        if data.get('amount_total') or data.get('amount_paid'):
            amount = int(data.get('amount_total') or data.get('amount_paid', 0))
            Invoice.objects.get_or_create(
                stripe_invoice_id=data.get('invoice') or data.get('id', 'inv_fallback'),
                defaults={
                    'user': user,
                    'amount_cents': amount,
                    'status': 'paid',
                    'invoice_date': timezone.now().date(),
                    'invoice_pdf_url': data.get('invoice_pdf', '')
                }
            )
        logger.info("Pro activated: user=%s with %d days access.", user.email, days_to_add)
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
        logger.info("Subscription expired: user=%s", sub.user_id)
    except Subscription.DoesNotExist:
        logger.warning("No subscription found for stripe_id=%s", stripe_sub_id)