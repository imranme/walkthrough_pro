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

app_name = 'payments'

urlpatterns = [
    path('start-trial/', StartTrialView.as_view(), name='start-trial'),
    path('subscription/', SubscriptionStatusView.as_view(), name='subscription-status'),
    path('create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create-checkout'),
    # path('verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('cancel/', CancelSubscriptionView.as_view(), name='cancel-subscription'),
    path('invoices/', InvoiceListView.as_view(), name='invoice-list'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]