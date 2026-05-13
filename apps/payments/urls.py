"""
URL Routing for the Payments Module.
────────────────────────────────────
Defines endpoints for trial management, Stripe checkout, billing history, 
and high-priority webhooks.
"""

from django.urls import path
from .views import (
    StartTrialView,
    SubscriptionStatusView,
    CreateCheckoutSessionView,
    VerifyPaymentView,
    CancelSubscriptionView,
    InvoiceListView,
    stripe_webhook,
)

app_name = 'payments' # Use this for namespacing in your project

urlpatterns = [
    # Trial Management: To be called right after user registration
    path('start-trial/', StartTrialView.as_view(), name='start-trial'),
    
    # Subscription Information: Checks active status and dashboard access
    path('subscription/', SubscriptionStatusView.as_view(), name='subscription-status'),
    
    # Stripe Checkout: Generates the hosted checkout URL for the Pro plan
    path('create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create-checkout'),
    
    # Client-Side Verification: Simple status check after payment success
    path('verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    
    # Cancellation: User-initiated cancellation for the next billing cycle
    path('cancel/', CancelSubscriptionView.as_view(), name='cancel-subscription'),
    
    # Billing History: Returns a list of past invoices/receipts
    path('invoices/', InvoiceListView.as_view(), name='invoice-list'),
    
    # Stripe Webhook: Server-to-Server endpoint (Must be CSRF-exempt in views)
    path('webhook/', stripe_webhook, name='stripe-webhook'),

    path('start-trial/', StartTrialView.as_view(), name='start-trial'),
]