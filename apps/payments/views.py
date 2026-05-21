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


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Webhook Signature Error: {e}")
        return HttpResponse(status=400)

    data = event['data']['object']
    if event['type'] == 'checkout.session.completed' or event['type'] == 'invoice.payment_succeeded':
        _activate_pro(data)
    
    return HttpResponse(status=200)


def _activate_pro(session):
    user_id = getattr(session, 'client_reference_id', None)
    if not user_id:
        metadata = getattr(session, 'metadata', {})
        user_id = metadata.get('user_id')

    if user_id:
        try:
            user = User.objects.get(pk=user_id)
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.plan_type = 'professional'
            sub.status = 'active'
            sub.pro_end_date = timezone.now() + timedelta(days=30)
            sub.save()
            return True
        except Exception as e:
            logger.error(f"Error activating pro: {e}")
    return False  




# import logging
# from datetime import date, timedelta

# import stripe
# from django.conf import settings
# from django.contrib.auth import get_user_model
# from django.http import HttpResponse
# from django.utils import timezone
# from django.views.decorators.csrf import csrf_exempt
# from rest_framework import generics, permissions, status
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from .models import Invoice, Subscription
# from .serializers import InvoiceSerializer

# logger = logging.getLogger(__name__)
# User   = get_user_model()


# def _is_admin(user) -> bool:
#     return bool(user and (user.is_staff or user.is_superuser))


# # 1. Start Free Trial
# class StartTrialView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         user = request.user

#         if user.is_superuser:
#             return Response({
#                 "message": "Superuser has permanent access.",
#                 "is_active": True,
#             })

#         if hasattr(user, 'subscription'):
#             sub = user.subscription
#             if sub.is_pro_active:
#                 return Response(
#                     {"message": "You already have an active Pro subscription."},
#                     status=400,
#                 )
#             if sub.is_trial_active:
#                 return Response({
#                     "message":        "Trial is already active.",
#                     "trial_end_date": sub.trial_end_date,
#                     "days_remaining": sub.trial_days_remaining,
#                 })
            
#             # Restart trial for old user
#             sub.plan_type        = 'free_trial'
#             sub.status           = 'trial'
#             sub.trial_start_date = timezone.now()
#             sub.trial_end_date   = timezone.now() + timedelta(days=5)
#             sub.save()
#             logger.info("Trial restarted: user=%s", user.pk)
#             return Response({
#                 "message":        "Your 5-day free trial has started!",
#                 "trial_end_date": sub.trial_end_date,
#                 "days_remaining": sub.trial_days_remaining,
#             }, status=201)

#         # Start new trial
#         sub = Subscription.objects.create(
#             user      = user,
#             plan_type = 'free_trial',
#             status    = 'trial',
#             trial_start_date = timezone.now(),
#             trial_end_date   = timezone.now() + timedelta(days=5)
#         )
#         logger.info("Trial started: user=%s expires=%s", user.pk, sub.trial_end_date)

#         return Response({
#             "message":        "Your 5-day free trial has started!",
#             "trial_end_date": sub.trial_end_date,
#             "days_remaining": sub.trial_days_remaining,
#         }, status=201)


# # 2. Subscription Status Check
# class SubscriptionStatusView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         if user.is_superuser:
#             return Response({
#                 "plan_type":            "superuser",
#                 "status":               "active",
#                 "is_active":            True,
#                 "is_trial_active":      True,
#                 "is_trial_expired":     False,
#                 "is_pro_active":        True,
#                 "days_remaining":       999,
#                 "trial_end_date":       None,
#                 "can_access_dashboard": True,
#                 "can_access_app":       True,
#                 "upgrade_url":          None,
#             })

#         if not hasattr(user, 'subscription'):
#             return Response({
#                 "plan_type":            None,
#                 "status":               "no_subscription",
#                 "is_active":            False,
#                 "is_trial_active":      False,
#                 "is_trial_expired":     False,
#                 "is_pro_active":        False,
#                 "days_remaining":       0,
#                 "trial_end_date":       None,
#                 "can_access_dashboard": False,
#                 "can_access_app":       False,
#                 "upgrade_url":          "https://walkthroughpro.app/pricing",
#                 "message":              "Start your free trial to get access.",
#             }, status=200)

#         sub = user.subscription
#         is_active = sub.is_active
#         is_admin  = _is_admin(user)

#         return Response({
#             "plan_type":            sub.plan_type,
#             "status":               sub.status,
#             "is_active":            is_active,
#             "is_trial_active":      sub.is_trial_active,
#             "is_trial_expired":     sub.is_trial_expired,
#             "is_pro_active":        sub.is_pro_active,
#             "days_remaining":       sub.trial_days_remaining,
#             "trial_end_date":       sub.trial_end_date,
#             "can_access_app":       is_active,
#             "can_access_dashboard": is_active and is_admin,
#             "upgrade_url":          "https://walkthroughpro.app/pricing" if not is_active else None,
#         })


# # 3. Create Stripe Checkout Session
# class CreateCheckoutSessionView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         stripe.api_key = settings.STRIPE_SECRET_KEY

#         if not settings.STRIPE_SECRET_KEY:
#             return Response({"error": "Stripe not configured."}, status=503)

#         user = request.user
#         try:
#             sub         = getattr(user, 'subscription', None)
#             customer_id = sub.stripe_customer_id if sub else None

#             if not customer_id:
#                 customer    = stripe.Customer.create(
#                     email    = user.email,
#                     name     = user.get_full_name() or user.username,
#                     metadata = {"django_user_id": str(user.pk)},
#                 )
#                 customer_id = customer.id
#                 if sub:
#                     sub.stripe_customer_id = customer_id
#                     sub.save(update_fields=['stripe_customer_id', 'updated_at'])

#             session = stripe.checkout.Session.create(
#                 customer             = customer_id,
#                 payment_method_types = ['card'],
#                 line_items           = [{'price': settings.STRIPE_PRO_PRICE_ID, 'quantity': 1}],
#                 mode                 = 'subscription',
#                 success_url          = f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
#                 cancel_url           = f"{settings.FRONTEND_URL}/pricing?cancelled=true",
#                 client_reference_id  = str(user.pk),
#                 allow_promotion_codes = True,
#             )
#             return Response({"url": session.url, "session_id": session.id})

#         except stripe.error.StripeError as exc:
#             return Response({"error": str(exc)}, status=400)


# # 4. Verify Payment on Success Page
# class VerifyPaymentView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         stripe.api_key = settings.STRIPE_SECRET_KEY
#         session_id     = request.data.get('session_id')

#         if not session_id:
#             return Response({"error": "session_id required."}, status=400)

#         try:
#             session = stripe.checkout.Session.retrieve(session_id)
#             if session.payment_status == 'paid':
#                 return Response({"status": "success", "message": "Payment verified."})
#             return Response({"status": "failed"}, status=400)
#         except stripe.error.StripeError as exc:
#             return Response({"error": str(exc)}, status=400)


# # 5. Get Invoice Billing History
# class InvoiceListView(generics.ListAPIView):
#     serializer_class   = InvoiceSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         return Invoice.objects.filter(user=self.request.user).order_by('-invoice_date')


# # 6. Cancel Subscription
# class CancelSubscriptionView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         stripe.api_key = settings.STRIPE_SECRET_KEY
#         try:
#             sub = request.user.subscription
#         except Subscription.DoesNotExist:
#             return Response({"error": "No subscription found."}, status=404)

#         if not sub.is_pro_active:
#             return Response({"error": "No active Pro subscription."}, status=400)

#         try:
#             stripe.Subscription.modify(
#                 sub.stripe_subscription_id,
#                 cancel_at_period_end=True,
#             )
#             sub.status = 'cancelled'
#             sub.save(update_fields=['status', 'updated_at'])
#             return Response({"message": "Subscription will cancel at period end."})
#         except stripe.error.StripeError as exc:
#             return Response({"error": str(exc)}, status=400)


# # 7. Stripe Webhook Handler
# @csrf_exempt
# def stripe_webhook(request):
#     stripe.api_key = settings.STRIPE_SECRET_KEY
#     payload        = request.body
#     sig_header     = request.META.get('HTTP_STRIPE_SIGNATURE', '')

#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
#         )
#     except (ValueError, stripe.error.SignatureVerificationError):
#         return HttpResponse(status=400)

#     event_type = event['type']
#     data       = event['data']['object']
#     logger.info("Stripe webhook: %s", event_type)

#     try:
#         if event_type == 'checkout.session.completed':
#             _activate_pro(data)
#         elif event_type == 'invoice.paid':
#             _save_invoice(data)
#         elif event_type == 'invoice.payment_failed':
#             _save_failed_invoice(data)
#         elif event_type == 'customer.subscription.deleted':
#             _deactivate_sub(data)
#     except Exception as exc:
#         logger.exception("Webhook handler error: %s", exc)

#     return HttpResponse(status=200)


# # Helper: Activate Pro Plan
# def _activate_pro(session):
#     user_id = session.get('client_reference_id') or session.get('metadata', {}).get('user_id')
#     if not user_id:
#         logger.error("Webhook: no user_id in session")
#         return
#     try:
#         user = User.objects.get(pk=user_id)
#         sub, _ = Subscription.objects.get_or_create(user=user)
#         sub.plan_type              = 'professional'
#         sub.status                 = 'active'
#         sub.stripe_customer_id     = session.get('customer')
#         sub.stripe_subscription_id = session.get('subscription')
#         sub.save()
#         logger.info("Pro activated: user=%s", user_id)
#     except Exception as exc:
#         logger.error("_activate_pro error: %s", exc)


# # Helper: Save Successful Invoice
# def _save_invoice(inv):
#     customer_id = inv.get('customer')
#     try:
#         sub  = Subscription.objects.get(stripe_customer_id=customer_id)
#         Invoice.objects.update_or_create(
#             stripe_invoice_id = inv['id'],
#             defaults={
#                 'user':            sub.user,
#                 'amount_cents':    inv.get('amount_paid', 0),
#                 'status':          'paid',
#                 'invoice_date':    date.fromtimestamp(inv.get('created', 0)),
#                 'invoice_pdf_url': inv.get('invoice_pdf', ''),
#             },
#         )
#     except Exception as exc:
#         logger.error("_save_invoice error: %s", exc)


# # Helper: Save Failed Invoice
# def _save_failed_invoice(inv):
#     customer_id = inv.get('customer')
#     try:
#         sub = Subscription.objects.get(stripe_customer_id=customer_id)
#         Invoice.objects.update_or_create(
#             stripe_invoice_id = inv['id'],
#             defaults={
#                 'user':         sub.user,
#                 'amount_cents': inv.get('amount_due', 0),
#                 'status':       'failed',
#                 'invoice_date': date.fromtimestamp(inv.get('created', 0)),
#             },
#         )
#     except Exception as exc:
#         logger.error("_save_failed_invoice error: %s", exc)


# # Helper: Deactivate Subscription
# def _deactivate_sub(sub_data):
#     try:
#         sub = Subscription.objects.get(stripe_subscription_id=sub_data['id'])
#         sub.status = 'expired'
#         sub.save(update_fields=['status', 'updated_at'])
#         logger.info("Subscription expired: user=%s", sub.user_id)
#     except Exception as exc:
#         logger.error("_deactivate_sub error: %s", exc)