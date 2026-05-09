import logging
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Invoice, Subscription
from .serializers import InvoiceSerializer, SubscriptionSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

# ══════════════════════════════════════════════════════════════════════
# 1. Start Trial: Initialize the 5-day window
# ══════════════════════════════════════════════════════════════════════
class StartTrialView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'subscription'):
            sub = request.user.subscription
            if sub.is_pro_active:
                return Response({"error": "Active Pro plan detected."}, status=400)
            if sub.is_trial_active:
                return Response({
                    "message": "Trial is already running.",
                    "days_remaining": sub.trial_days_remaining
                })

        sub = Subscription.objects.create(
            user=request.user,
            plan_type='free_trial',
            status='trial',
        )
        return Response({
            "message": "5-day free trial started!",
            "trial_end_date": sub.trial_end_date,
            "days_remaining": sub.trial_days_remaining,
        }, status=status.HTTP_201_CREATED)

# ══════════════════════════════════════════════════════════════════════
# 2. Subscription Status: Access decision endpoint
# ══════════════════════════════════════════════════════════════════════
class SubscriptionStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return Response({"has_subscription": False}, status=404)

        return Response({
            "plan_type": sub.plan_type,
            "status": sub.status,
            "is_fully_active": sub.is_fully_active,
            "can_access_dashboard": sub.can_access_dashboard,
            "trial_days_remaining": sub.trial_days_remaining,
        })

# ══════════════════════════════════════════════════════════════════════
# 3. Stripe Checkout: Payment Session Generation
# ══════════════════════════════════════════════════════════════════════
class CreateCheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
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
            )
            return Response({"url": session.url, "session_id": session.id})
        except Exception as e:
            return Response({"error": str(e)}, status=400)

# ══════════════════════════════════════════════════════════════════════
# 4. New Views: Needed for URLs
# ══════════════════════════════════════════════════════════════════════
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
        # লজিক আপনার প্রয়োজন অনুযায়ী আপডেট করে নিন
        return Response({"message": "Cancellation request received."})

class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Invoice.objects.filter(subscription__user=self.request.user)

# ══════════════════════════════════════════════════════════════════════
# 5. Stripe Webhook
# ══════════════════════════════════════════════════════════════════════
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return HttpResponse(status=400)

    data = event['data']['object']
    if event['type'] == 'checkout.session.completed':
        _activate_pro(data)
    
    return HttpResponse(status=200)

def _activate_pro(session):
    user_id = session.get('client_reference_id')
    try:
        user = User.objects.get(pk=user_id)
        sub = user.subscription
        sub.plan_type = 'professional'
        sub.status = 'active'
        sub.stripe_subscription_id = session.get('subscription')
        sub.save()
    except Exception as e:
        logger.error(f"Error: {e}")