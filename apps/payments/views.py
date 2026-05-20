# import logging
# import stripe
# from django.conf import settings
# from django.contrib.auth import get_user_model
# from django.http import HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from rest_framework import generics, permissions, status
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from .models import Invoice, Subscription
# from .serializers import InvoiceSerializer, SubscriptionSerializer

# # API Key Global কনফিগারেশন
# stripe.api_key = settings.STRIPE_SECRET_KEY
# logger = logging.getLogger(__name__)
# User = get_user_model()

# # ══════════════════════════════════════════════════════════════════════
# # 1. Start Trial: Initialize the 5-day window
# # ══════════════════════════════════════════════════════════════════════
# class StartTrialView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         if hasattr(request.user, 'subscription'):
#             sub = request.user.subscription
#             if sub.status == 'active': # লজিক সহজ করা হলো
#                 return Response({"error": "Active Pro plan detected."}, status=400)
#             if sub.status == 'trial':
#                 return Response({
#                     "message": "Trial is already running.",
#                     "days_remaining": sub.trial_days_remaining
#                 })

#         # নতুন ট্রায়াল তৈরি
#         sub = Subscription.objects.create(
#             user=request.user,
#             plan_type='free_trial',
#             status='trial',
#         )
#         return Response({
#             "message": "5-day free trial started!",
#             "trial_end_date": sub.trial_end_date,
#             "days_remaining": sub.trial_days_remaining,
#         }, status=status.HTTP_201_CREATED)

# # ══════════════════════════════════════════════════════════════════════
# # 2. Subscription Status: Access decision endpoint
# # ══════════════════════════════════════════════════════════════════════
# class SubscriptionStatusView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         try:
#             sub = request.user.subscription
#         except Subscription.DoesNotExist:
#             return Response({"has_subscription": False}, status=404)

#         return Response({
#             "plan_type": sub.plan_type,
#             "status": sub.status,
#             "is_fully_active": sub.is_fully_active,
#             # এটি নিশ্চিত করবে যে ট্রায়াল বা একটিভ—উভয় ক্ষেত্রেই এক্সেস পাবে
#             "can_access_dashboard": sub.status in ['active', 'trial'], 
#             "trial_days_remaining": sub.trial_days_remaining,
#         })

# # ══════════════════════════════════════════════════════════════════════
# # 3. Stripe Checkout: Payment Session Generation
# # ══════════════════════════════════════════════════════════════════════
# class CreateCheckoutSessionView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         try:
#             sub = getattr(user, 'subscription', None)
#             customer_id = sub.stripe_customer_id if sub else None

#             # কাস্টমার না থাকলে তৈরি করা
#             if not customer_id:
#                 customer = stripe.Customer.create(email=user.email, name=user.username)
#                 customer_id = customer.id
#                 if sub:
#                     sub.stripe_customer_id = customer_id
#                     sub.save(update_fields=['stripe_customer_id'])

#             session = stripe.checkout.Session.create(
#                 customer=customer_id,
#                 payment_method_types=['card'],
#                 line_items=[{'price': settings.STRIPE_PRO_PRICE_ID, 'quantity': 1}],
#                 mode='subscription',
#                 success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
#                 cancel_url=f"{settings.FRONTEND_URL}/pricing",
#                 client_reference_id=str(user.pk),
#                 metadata={'user_id': str(user.pk)},
#             )
#             return Response({"url": session.url, "session_id": session.id})
#         except Exception as e:
#             return Response({"error": str(e)}, status=400)

# # ══════════════════════════════════════════════════════════════════════
# # 4. New Views: Verify, Cancel & Invoices
# # ══════════════════════════════════════════════════════════════════════
# class VerifyPaymentView(APIView):
#     permission_classes = [permissions.IsAuthenticated]
#     def get(self, request):
#         sub = getattr(request.user, 'subscription', None)
#         if sub and sub.status == 'active':
#             return Response({"status": "success", "message": "Verified!"})
#         return Response({"status": "pending"}, status=202)

# class CancelSubscriptionView(APIView):
#     permission_classes = [permissions.IsAuthenticated]
#     def post(self, request):
#         # এখানে স্ট্রাইপ ক্যান্সেল লজিক পরবর্তীতে যোগ করতে পারবেন
#         return Response({"message": "Cancellation request received."})

# class InvoiceListView(generics.ListAPIView):
#     serializer_class = InvoiceSerializer
#     permission_classes = [permissions.IsAuthenticated]
#     def get_queryset(self):
#         return Invoice.objects.filter(subscription__user=self.request.user)

# # ══════════════════════════════════════════════════════════════════════
# # 5. Stripe Webhook
# # ══════════════════════════════════════════════════════════════════════
# @csrf_exempt
# def stripe_webhook(request):
#     payload = request.body
#     sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
#         )
#     except Exception as e:
#         logger.error(f"Webhook Signature Error: {e}")
#         return HttpResponse(status=400)

#     data = event['data']['object']
#     if event['type'] == 'checkout.session.completed':
#         _activate_pro(data)
    
#     return HttpResponse(status=200)

# def _activate_pro(session):
#     # StripeObject থেকে ডাটা নেয়ার সঠিক নিয়ম
#     user_id = getattr(session, 'client_reference_id', None)
#     if not user_id:
#         metadata = getattr(session, 'metadata', {})
#         user_id = metadata.get('user_id')

#     if user_id:
#         try:
#             from apps.payments.models import Subscription
#             from django.contrib.auth import get_user_model
#             User = get_user_model()
#             user = User.objects.get(pk=user_id)
            
#             sub, _ = Subscription.objects.get_or_create(user=user)
#             sub.plan_type = 'professional'
#             sub.status = 'active'
#             sub.save()
#             return True
#         except Exception as e:
#             print(f"Error: {e}")
#     return False 

# class InvoiceListView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         try:
#             # এখানে 'subscription' নয়, 'user' ব্যবহার করতে হবে
#             invoices = Invoice.objects.filter(user=request.user).order_by('-invoice_date')
            
#             # আপনি যদি কোনো সিরিয়ালাইজার ব্যবহার করেন:
#             from .serializers import InvoiceSerializer
#             serializer = InvoiceSerializer(invoices, many=True)
#             return Response(serializer.data, status=200)

#         except Exception as e:
#             # এরর হলে সেটি যেন রেসপন্সে দেখা যায়
#             return Response({"error": str(e)}, status=500) 



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