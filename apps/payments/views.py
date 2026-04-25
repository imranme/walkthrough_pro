import stripe
import logging
from datetime import date

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics

from .models import Subscription, Invoice
from .serializers import InvoiceSerializer, SubscriptionSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

# ══════════════════════════════════════════════════════════════════════════════
# 1. StartTrialView - Initializes 5-day trial
# ══════════════════════════════════════════════════════════════════════════════

class StartTrialView(APIView):
    """
    Initializes a 5-day free trial for a newly registered user.
    Prevents multiple trial creation for the same user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'subscription'):
            return Response(
                {"message": "Subscription record already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sub = Subscription.objects.create(user=request.user)
        return Response({
            "message": "Your 5-day free trial has started!",
            "trial_end_date": sub.trial_end_date,
        }, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════════════════════════
# 2. SubscriptionStatusView - Current plan details
# ══════════════════════════════════════════════════════════════════════════════

class SubscriptionStatusView(APIView):
    """
    Returns the current plan type and status.
    Provides the upgrade URL if the trial is expired.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return Response({"error": "No subscription found."}, status=404)

        return Response({
            "plan_type":   sub.plan_type,
            "status":      sub.status,
            "is_active":   sub.is_active,
            "trial_end_date": sub.trial_end_date,
            "upgrade_url": "https://walkthroughpro.com/pricing",
        })


# ══════════════════════════════════════════════════════════════════════════════
# 3. CreateCheckoutSessionView - Stripe Redirect
# ══════════════════════════════════════════════════════════════════════════════

class CreateCheckoutSessionView(APIView):
    """
    Creates a Stripe Checkout session and returns the URL.
    The frontend should redirect the user to this URL for payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': settings.STRIPE_PRO_PRICE_ID,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing",
                client_reference_id=str(request.user.id),
            )
            return Response({'url': session.url})
        except stripe.error.StripeError as e:
            logger.error(f"Stripe Session Error: {str(e)}")
            return Response({'error': str(e)}, status=400)


# ══════════════════════════════════════════════════════════════════════════════
# 4. InvoiceListView - Billing History
# ══════════════════════════════════════════════════════════════════════════════

class InvoiceListView(generics.ListAPIView):
    """Returns a list of all paid/failed invoices for the current user."""
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Stripe Webhook - Asynchronous Updates
# ══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
def stripe_webhook(request):
    """
    Listens to Stripe events to activate Pro plans and record invoices.
    Must be configured in Stripe Dashboard/CLI.
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    # A. User completes payment successfully
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')

        try:
            user = User.objects.get(pk=user_id)
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.plan_type = 'professional'
            sub.status    = 'active'
            sub.stripe_subscription_id = session.get('subscription')
            sub.save()
            logger.info(f"User {user_id} upgraded to Professional.")
        except Exception as e:
            logger.error(f"Upgrade Error for user {user_id}: {e}")

    # B. Payment record (Invoice) is generated
    elif event['type'] == 'invoice.paid':
        inv_data = event['data']['object']
        stripe_sub_id = inv_data.get('subscription')

        try:
            # Find user based on the subscription ID stored in our DB
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            Invoice.objects.update_or_create(
                stripe_invoice_id=inv_data['id'],
                defaults={
                    'user': sub.user,
                    'amount_cents': inv_data.get('amount_paid', 0),
                    'status': 'paid',
                    'invoice_date': date.fromtimestamp(inv_data.get('created', 0)),
                    'invoice_pdf_url': inv_data.get('invoice_pdf', ''),
                },
            )
        except Exception as e:
            logger.error(f"Invoice logging failed: {e}")

    # C. Subscription expires or is cancelled
    elif event['type'] == 'customer.subscription.deleted':
        sub_data = event['data']['object']
        try:
            sub = Subscription.objects.get(stripe_subscription_id=sub_data['id'])
            sub.status = 'expired'
            sub.save()
            logger.info(f"Subscription {sub_data['id']} marked as expired.")
        except Subscription.DoesNotExist:
            pass

    return HttpResponse(status=200)