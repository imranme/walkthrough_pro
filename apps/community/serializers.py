from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils.timesince import timesince
from .models import Discussion, Answer, Reply

# class AuthorSerializer(serializers.ModelSerializer):
#     full_name = serializers.CharField(source='get_full_name', read_only=True)
#     initials = serializers.SerializerMethodField()
#     role = serializers.CharField(source='profile.get_role_display', default="Member")

#     class Meta:
#         model = User
#         fields = ["id", "full_name", "initials", "role"]

#     def get_initials(self, obj):
#         if obj.first_name and obj.last_name:
#             f = str(obj.first_name)
#             l = str(obj.last_name)
#             return (f + l).upper()

class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    initials = serializers.SerializerMethodField()
    role = serializers.CharField(source='profile.get_role_display', default="Member")

    class Meta:
        model = User
        fields = ["id", "full_name", "initials", "role"]

    def get_initials(self, obj):
        # নামের প্রথম এবং শেষ অক্ষরের প্রথম লেটার নিয়ে SM স্টাইল বানানো
        f = str(obj.first_name) if obj.first_name else ""
        l = str(obj.last_name) if obj.last_name else ""
        
        if not f and not l:
            return obj.username.upper() if obj.username else "U"
        return (f + l).upper()
     

class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(source="user", read_only=True)
    class Meta:
        model = Reply
        fields = ["id", "author", "body", "created_at"]

class AnswerSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(source="user", read_only=True)
    replies = ReplySerializer(many=True, read_only=True)
    class Meta:
        model = Answer
        fields = ["id", "author", "body", "replies", "created_at"]

# class DiscussionListSerializer(serializers.ModelSerializer):
#     author = AuthorSerializer(source="user", read_only=True)
#     time_since = serializers.SerializerMethodField()
#     reply_count = serializers.SerializerMethodField()

#     class Meta:
#         model = Discussion
#         fields = ["id", "title", "body", "category", "view_count", "reply_count", "is_answered", "author", "time_since"]

#     # def get_time_since(self, obj):
#     #     return f"{timesince(obj.created_at).split(',')} ago"
#     def get_time_since(self, obj):
#         delta = timesince(obj.created_at).split(',')[0]
#         return f"{delta} ago"
    
#     def get_reply_count(self, obj):
#         return obj.answers.count() + Reply.objects.filter(answer__discussion=obj).count()

class DiscussionDetailSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(source="user", read_only=True)
    answers = AnswerSerializer(many=True, read_only=True)
    time_since = serializers.SerializerMethodField() # যোগ করুন
    reply_count = serializers.SerializerMethodField() # যোগ করুন

    class Meta:
        model = Discussion
        fields = ["id", "title", "body", "category", "view_count", "reply_count", "author", "answers", "time_since", "created_at"]

    def get_time_since(self, obj):
        return f"{timesince(obj.created_at).split(',')} ago"
    
    def get_reply_count(self, obj):
        return obj.answers.count() + Reply.objects.filter(answer__discussion=obj).count()

class DiscussionDetailSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(source="user", read_only=True)
    answers = AnswerSerializer(many=True, read_only=True)
    class Meta:
        model = Discussion
        fields = ["id", "title", "body", "category", "view_count", "author", "answers", "created_at"]

class DiscussionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discussion
        fields = ["title", "body", "category"]

class AnswerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ["body"]

class ReplyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reply
        fields = ["id", "body", "user", "answer", "created_at"]
        read_only_fields = ["user", "answer"]