from rest_framework import serializers
from .models import Invoice, Subscription

class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializes subscription data including the calculated active status.
    Used for showing the current plan on the dashboard.
    """
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = ('plan_type', 'status', 'is_active', 'trial_end_date')


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializes billing history. 
    Uses the model property to display formatted currency.
    """
    amount_display = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'stripe_invoice_id', 
            'amount_display', 
            'status', 
            'invoice_date', 
            'invoice_pdf_url'
        )