from django.contrib import admin
# Circular Import এড়াতে সম্পূর্ণ পাথ (Absolute Path) ব্যবহার করা হলো
from apps.payments.models import Subscription, Invoice

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # list_display: অ্যাডমিন টেবিলের প্রধান কলামগুলো দেখাবে
    # এখানে 'is_trial_active' মডেল প্রপার্টিটি অ্যাডমিন প্যানেলে দারুণ কাজ করবে
    list_display = ('user', 'plan_type', 'status', 'is_trial_active', 'created_at')
    
    # list_filter: ডানপাশে ফিল্টার করার অপশন দিবে
    list_filter = ('plan_type', 'status')
    
    # FIXED: readonly_fields থেকে 'trial_end_date' সরিয়ে নেওয়া হয়েছে।
    # এটি না সরালে আমাদের মডেলের নতুন save() মেথডের অটো-ক্যালকুলেশন অ্যাডমিন প্যানেল থেকে কাজ করবে না।
    readonly_fields = ('created_at', 'updated_at')
    
    # search_fields: ইউজার ইমেইল ও ইউজারনেম দিয়ে সার্চ করার জন্য
    search_fields = ('user__email', 'user__username')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    # আপনার মডেলের সঠিক ফিল্ড এবং কাস্টম ডিসপ্লে মেথড এখানে ব্যবহার করা হয়েছে
    list_display = ('user', 'stripe_invoice_id', 'amount_display_field', 'status', 'invoice_date')
    
    list_filter = ('status', 'invoice_date')
    readonly_fields = ('created_at',)
    search_fields = ('stripe_invoice_id', 'user__email')

    # কাস্টম মেথডের নাম একটু পরিবর্তন করা হলো যেন list_display-এর সাথে নাম কনফ্লিক্ট না করে
    def amount_display_field(self, obj):
        return obj.amount_display
    amount_display_field.short_description = 'Amount'