from django.contrib import admin
from .models import Discussion, Answer, Reply

# Discussion মডেলটি অ্যাডমিন প্যানেলে সুন্দরভাবে দেখানোর জন্য
@admin.register(Discussion)
class DiscussionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'view_count', 'created_at') # কোন কোন কলাম দেখাবে
    list_filter = ('category', 'created_at') # ডানপাশে ফিল্টার অপশন
    search_fields = ('title', 'body') # সার্চ বক্স
    ordering = ('-created_at',) # সিরিয়াল

# Answer মডেল রেজিস্ট্রেশন
@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('discussion', 'user', 'created_at')
    search_fields = ('body',)

# Reply মডেল রেজিস্ট্রেশন
@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('answer', 'user', 'created_at')
    search_fields = ('body',)