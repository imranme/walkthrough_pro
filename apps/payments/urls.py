from django.urls import path
from .views import (
    StartTrialView,
    SubscriptionStatusView,
    CreateCheckoutSessionView,
    InvoiceListView,
    stripe_webhook,
)

urlpatterns = [
    path('start-trial/',              StartTrialView.as_view(),             name='start-trial'),
    path('subscription/',             SubscriptionStatusView.as_view(),     name='subscription-status'),
    path('create-checkout-session/',  CreateCheckoutSessionView.as_view(),  name='create-checkout-session'),
    path('invoices/',                 InvoiceListView.as_view(),            name='invoice-list'),
    path('webhook/',                  stripe_webhook,                       name='stripe-webhook'),
]