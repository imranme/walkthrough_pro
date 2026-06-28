# """
# Serializers for Subscription and Billing Data.
# ──────────────────────────────────────────────
# Converts Subscription and Invoice models into JSON format for API responses.
# Includes read-only calculated properties for front-end logic.
# """

# from rest_framework import serializers
# from .models import Invoice, Subscription


# class SubscriptionSerializer(serializers.ModelSerializer):
#     """
#     Serializes user subscription details, including trial status 
#      and expiration calculations. All fields are read-only to 
#      prevent unauthorized state changes via API.
#     """
#     # Exposing model properties as boolean fields
#     is_trial_active = serializers.BooleanField(read_only=True)
#     is_trial_expired = serializers.BooleanField(read_only=True)
#     is_pro_active = serializers.BooleanField(read_only=True)
#     is_fully_active = serializers.BooleanField(read_only=True)
#     trial_days_remaining = serializers.IntegerField(read_only=True)

#     class Meta:
#         model = Subscription
#         fields = (
#             'plan_type', 
#             'status',
#             'trial_end_date', 
#             'trial_days_remaining',
#             'is_trial_active', 
#             'is_trial_expired',
#             'is_pro_active', 
#             'is_fully_active',
#         )
#         # Ensuring all data sent to the frontend is immutable via this serializer
#         read_only_fields = fields


# class InvoiceSerializer(serializers.ModelSerializer):
#     """
#     Serializes billing history (Invoices).
#     Used to display the list of past payments in the user settings.
#     """
#     # Formatted dollar string (e.g., "$9.99") from the model property
#     amount_display = serializers.CharField(read_only=True)

#     class Meta:
#         model = Invoice
#         fields = (
#             'stripe_invoice_id', 
#             'amount_display',
#             'status', 
#             'invoice_date', 
#             'invoice_pdf_url',
#         )
#         read_only_fields = ('stripe_invoice_id', 'amount_display', 'status', 'invoice_date', 'invoice_pdf_url')











"""
apps/payments/serializers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Serializers for Subscription and Billing Data.
"""

from rest_framework import serializers
from .models import Invoice, Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializes user subscription details, including trial status 
    and expiration calculations. All fields are read-only.
    """
    is_trial_active = serializers.BooleanField(read_only=True)
    is_trial_expired = serializers.BooleanField(read_only=True)
    is_pro_active = serializers.BooleanField(read_only=True)
    is_fully_active = serializers.BooleanField(read_only=True)
    trial_days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            'plan_type', 
            'status',
            'trial_end_date', 
            'trial_days_remaining',
            'is_trial_active', 
            'is_trial_expired',
            'is_pro_active', 
            'is_fully_active',
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializes billing history (Invoices).
    """
    amount_display = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'stripe_invoice_id', 
            'amount_display',
            'status', 
            'invoice_date', 
            'invoice_pdf_url',
        )
        read_only_fields = fields