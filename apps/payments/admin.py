from django.contrib import admin
from .models import Subscription, Invoice

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # list_display: অ্যাডমিন টেবিলের কলামগুলো দেখাবে
    list_display = ('user', 'plan_type', 'status', 'is_trial_active', 'created_at')
    
    # list_filter: ডানপাশে ফিল্টার করার অপশন দিবে
    list_filter = ('plan_type', 'status')
    
    # readonly_fields: যে ফিল্ডগুলো অ্যাডমিন থেকে এডিট করা যাবে না
    readonly_fields = ('trial_end_date', 'created_at', 'updated_at')
    
    # search_fields: ইউজার ইমেইল দিয়ে সার্চ করার জন্য
    search_fields = ('user__email', 'user__username')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    # আপনার মডেলে 'amount' নেই, আছে 'amount_cents' 
    # এবং 'subscription' নেই, আছে 'user'
    list_display = ('user', 'stripe_invoice_id', 'amount_display', 'status', 'invoice_date')
    
    list_filter = ('status', 'invoice_date')
    
    # readonly_fields এ আপনার মডেলের সঠিক ফিল্ড নামগুলো দেওয়া হয়েছে
    readonly_fields = ('created_at',)
    
    search_fields = ('stripe_invoice_id', 'user__email')

    # মডেলে থাকা amount_display প্রপার্টিকে অ্যাডমিনে দেখানোর জন্য
    def amount_display(self, obj):
        return obj.amount_display
    amount_display.short_description = 'Amount'