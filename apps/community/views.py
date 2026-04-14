from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import F, Count, Q
from .models import Answer, Discussion, Reply
from .serializers import *

class CommunityStatsView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        total_discussions = Discussion.objects.count()
        total_answered = Discussion.objects.annotate(ans_count=Count('answers')).filter(ans_count__gt=0).count()
        total_replies = Answer.objects.count() + Reply.objects.count()
        return Response({
            "total_discussions": total_discussions,
            "total_answered": total_answered,
            "total_replies": total_replies,
        })

class DiscussionListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    def get_serializer_class(self):
        return DiscussionCreateSerializer if self.request.method == "POST" else DiscussionListSerializer

    def get_queryset(self):
        qs = Discussion.objects.select_related("user").order_by("-created_at")
        search = self.request.query_params.get("search")
        if search: qs = qs.filter(Q(title__icontains=search) | Q(body__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class DiscussionDetailView(generics.RetrieveAPIView):
    queryset = Discussion.objects.all()
    serializer_class = DiscussionDetailSerializer
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Discussion.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        instance.refresh_from_db()
        return super().retrieve(request, *args, **kwargs)

class AnswerCreateView(generics.CreateAPIView):
    serializer_class = AnswerCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        discussion = Discussion.objects.get(pk=self.kwargs.get("discussion_id"))
        serializer.save(user=self.request.user, discussion=discussion)

class ReplyCreateView(generics.CreateAPIView):
    serializer_class = ReplyCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        answer = Answer.objects.get(pk=self.kwargs.get("answer_id"))
        serializer.save(user=self.request.user, answer=answer)