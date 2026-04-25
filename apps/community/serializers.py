from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils.timesince import timesince
from .models import Discussion, Answer, Reply

class AuthorSerializer(serializers.ModelSerializer):
    """Serializes user info for posts and comments."""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    initials = serializers.SerializerMethodField()
    role = serializers.CharField(source='profile.get_role_display', default="Member")

    class Meta:
        model = User
        fields = ["id", "full_name", "initials", "role"]

    def get_initials(self, obj):
        # Generate initials like 'JD' from first and last name
        f = str(obj.first_name) if obj.first_name else ""
        l = str(obj.last_name) if obj.last_name else ""
        
        if not f and not l:
            return obj.username.upper() if obj.username else "U"
        
        # Take first character from each name
        f_initial = f if f else ""
        l_initial = l if l else ""
        return (f_initial + l_initial).upper()

class ReplySerializer(serializers.ModelSerializer):
    """Serializer for nested replies."""
    author = AuthorSerializer(source="user", read_only=True)
    class Meta:
        model = Reply
        fields = ["id", "author", "body", "created_at"]

class AnswerSerializer(serializers.ModelSerializer):
    """Serializer for nested answers/comments."""
    author = AuthorSerializer(source="user", read_only=True)
    replies = ReplySerializer(many=True, read_only=True)
    class Meta:
        model = Answer
        fields = ["id", "author", "body", "replies", "created_at"]

class DiscussionListSerializer(serializers.ModelSerializer):
    """
    REQUIRED: Used for the community feed list view.
    Fixes the 'NameError' in views.py.
    """
    author = AuthorSerializer(source="user", read_only=True)
    time_since = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Discussion
        fields = ["id", "title", "body", "category", "view_count", "reply_count", "author", "time_since", "created_at"]

    def get_time_since(self, obj):
        try:
            return f"{timesince(obj.created_at).split(',')} ago"
        except Exception:
            return "Just now"

    def get_reply_count(self, obj):
        # Total count of answers and their subsequent replies
        return obj.answers.count() + Reply.objects.filter(answer__discussion=obj).count()

class DiscussionDetailSerializer(serializers.ModelSerializer):
    """Detailed view for a single discussion including all nested answers."""
    author = AuthorSerializer(source="user", read_only=True)
    answers = AnswerSerializer(many=True, read_only=True)
    class Meta:
        model = Discussion
        fields = ["id", "title", "body", "category", "view_count", "author", "answers", "created_at"]

class DiscussionCreateSerializer(serializers.ModelSerializer):
    """Handles new discussion creation."""
    class Meta:
        model = Discussion
        fields = ["title", "body", "category"]

class AnswerCreateSerializer(serializers.ModelSerializer):
    """Handles new comment/answer creation."""
    class Meta:
        model = Answer
        fields = ["body"]

class ReplyCreateSerializer(serializers.ModelSerializer):
    """Handles new reply creation."""
    class Meta:
        model = Reply
        fields = ["id", "body", "user", "answer", "created_at"]
        read_only_fields = ["user", "answer"]