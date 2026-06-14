import logging
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import Invoice, Subscription
from .serializers import InvoiceSerializer
from .permissions import _is_mobile_request

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)
User = get_user_model()

class StartTrialView(APIView):
    """৫ দিনের ট্রায়াল পিরিয়ড স্টার্ট করার সেফ এপিআই এন্ডপয়েন্ট।"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_staff or user.is_superuser:
            return Response({"message": "Perpetual staff access. No trial needed."}, status=200)

        sub, created = Subscription.objects.get_or_create(user=user)

        if not created:
            if sub.status == 'active' or sub.plan_type == 'professional':
                return Response({"error": "Active Professional plan detected."}, status=400)
            if sub.status == 'trial' and sub.is_trial_active:
                return Response({
                    "message": "Trial is already running.",
                    "days_remaining": sub.trial_days_remaining
                })
            if sub.status == 'expired' or not sub.is_trial_active:
                return Response({
                    "error": "trial_expired", 
                    "message": "Your 5-day trial has already expired. Please upgrade to Pro."
                }, status=400)

        # ট্রায়াল ডাটা প্রিপেয়ার ও সেভ
        sub.plan_type = 'free_trial'
        sub.status = 'trial'
        sub.trial_start_date = timezone.now()
        sub.trial_end_date = timezone.now() + timedelta(days=5)
        sub.save()

        return Response({
            "message": "5-day free trial started!",
            "trial_end_date": sub.trial_end_date,
            "days_remaining": sub.trial_days_remaining,
        }, status=status.HTTP_201_CREATED)


class SubscriptionStatusView(APIView):
    """ফ্রন্টএন্ড এই এপিআই কল করে ডিসিশন নেবে স্ক্রিন লক করবে নাকি ইউজারকে ভেতরে রাখবে।"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        if user.is_staff or user.is_superuser:
            return Response({
                "plan_type": "professional",
                "status": "active",
                "is_fully_active": True,
                "can_access_dashboard": True,
                "trial_days_remaining": 0,
                "force_logout": False
            }, status=200)

        try:
            sub = user.subscription
        except Subscription.DoesNotExist:
            return Response({"has_subscription": False, "is_fully_active": False, "force_logout": False}, status=200)

        is_observer = hasattr(user, 'profile') and getattr(user.profile, 'is_observer', False)
        active_access = sub.has_app_access 
        can_access_db = active_access and not is_observer

        # মোবাইল রিকোয়েস্টের জন্য ট্রায়াল শেষ হলে force_logout True যাবে
        force_logout_user = not active_access and _is_mobile_request(request)

        return Response({
            "plan_type": sub.plan_type,
            "status": sub.status,
            "is_fully_active": active_access,
            "can_access_dashboard": can_access_db, 
            "trial_days_remaining": sub.trial_days_remaining,
            "force_logout": force_logout_user,
            "role": "observer" if is_observer else "admin"
        }, status=200)


class CreateCheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            sub = getattr(user, 'subscription', None)
            customer_id = sub.stripe_customer_id if sub else None

            if not customer_id:
                customer = stripe.Customer.create(email=user.email, name=user.username)
                customer_id = customer.id
                if sub:
                    sub.stripe_customer_id = customer_id
                    sub.save(update_fields=['stripe_customer_id'])

            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{'price': settings.STRIPE_PRO_PRICE_ID, 'quantity': 1}],
                mode='subscription',
                success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing",
                client_reference_id=str(user.pk),
                metadata={'user_id': str(user.pk)},
            )
            return Response({"url": session.url, "session_id": session.id})
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class VerifyPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        sub = getattr(request.user, 'subscription', None)
        if sub and sub.status == 'active':
            return Response({"status": "success", "message": "Verified!"})
        return Response({"status": "pending"}, status=202)


class CancelSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        return Response({"message": "Cancellation request received."})


class InvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            invoices = Invoice.objects.filter(user=request.user).order_by('-invoice_date')
            serializer = InvoiceSerializer(invoices, many=True)
            return Response(serializer.data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# @csrf_exempt
# def stripe_webhook(request):
#     payload    = request.body
#     sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
#         )
#     except Exception as e:
#         logger.error("Webhook signature error: %s", e)
#         return HttpResponse(status=400)

#     event_type = event['type']
#     # StripeObject → raw dict
#     raw_data = event['data']['object']
#     data = raw_data if isinstance(raw_data, dict) else dict(raw_data)

#     logger.info("Webhook: %s", event_type)

#     if event_type in ('checkout.session.completed', 'invoice.paid'):
#         _activate_pro(data)

#     return HttpResponse(status=200)


# def _activate_pro(session):
#     # StripeObject → dict convert করতে হবে
#     if hasattr(session, '_data'):
#         session = dict(session._data)
#     elif hasattr(session, 'to_dict'):
#         session = session.to_dict()

#     user_id = (
#         session.get('client_reference_id')
#         or (session.get('metadata') or {}).get('user_id')
#     )

#     logger.info("_activate_pro: user_id=%s", user_id)

#     if not user_id:
#         logger.error("No user_id in webhook: %s", session)
#         return False

#     try:
#         user = User.objects.get(pk=user_id)
#         sub, _ = Subscription.objects.get_or_create(user=user)
#         sub.plan_type              = 'professional'
#         sub.status                 = 'active'
#         sub.stripe_subscription_id = session.get('subscription')
#         sub.stripe_customer_id     = session.get('customer')
#         sub.pro_end_date           = timezone.now() + timedelta(days=30)
#         sub.save()
#         logger.info("Pro activated: user=%s", user.email)
#         return True
#     except User.DoesNotExist:
#         logger.error("User not found: pk=%s", user_id)
#     except Exception as e:
#         logger.error("_activate_pro error: %s", e)
#     return False



@csrf_exempt
def stripe_webhook(request):
    payload    = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error("Webhook signature error: %s", e)
        return HttpResponse(status=400)

    event_type = event['type']
    raw_data = event['data']['object']
    
    # StripeObject কে নিরাপদে deep dict এ রূপান্তর করার সঠিক নিয়ম
    if hasattr(raw_data, 'to_dict_deep'):
        data = raw_data.to_dict_deep()
    elif hasattr(raw_data, 'to_dict'):
        data = raw_data.to_dict()
    else:
        data = dict(raw_data)

    logger.info("Webhook: %s", event_type)

    # টেস্ট এবং লাইভ উভয় ক্ষেত্রে এই ৩টি ইভেন্ট হ্যান্ডেল করা নিরাপদ
    if event_type in ('checkout.session.completed', 'invoice.paid', 'invoice.payment_succeeded'):
        _activate_pro(data)

    return HttpResponse(status=200)


def _activate_pro(session):
    # ডাবল সেফটি চেক: ডাটা ডিকশনারি না হলে রূপান্তর করে নেওয়া
    if hasattr(session, 'to_dict_deep'):
        session = session.to_dict_deep()
    elif hasattr(session, 'to_dict'):
        session = session.to_dict()
    elif not isinstance(session, dict):
        session = dict(session)

    # ডাটা থেকে নিরাপদে user_id বের করা
    user_id = (
        session.get('client_reference_id')
        or session.get('metadata', {}).get('user_id')
    )

    logger.info("_activate_pro: user_id=%s", user_id)

    if not user_id:
        logger.error("No user_id in webhook: %s", session)
        return False

    try:
        user = User.objects.get(pk=user_id)
        sub, _ = Subscription.objects.get_or_create(user=user)
        sub.plan_type              = 'professional'
        sub.status                 = 'active'
        sub.stripe_subscription_id = session.get('subscription')
        sub.stripe_customer_id     = session.get('customer')
        sub.pro_end_date           = timezone.now() + timedelta(days=30)
        sub.save()
        logger.info("Pro activated: user=%s", user.email)
        return True
    except User.DoesNotExist:
        logger.error("User not found: pk=%s", user_id)
    except Exception as e:
        logger.error("_activate_pro error: %s", e)
    return False