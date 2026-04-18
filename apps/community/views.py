# from rest_framework import generics, permissions, status
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from django.db.models import F, Count, Q
# from .models import Answer, Discussion, Reply
# from .serializers import *
# from django.shortcuts import get_object_or_404
# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework import filters

# class CommunityStatsView(APIView):
#     permission_classes = [permissions.AllowAny]
#     def get(self, request):
#         total_discussions = Discussion.objects.count()
#         total_answered = Discussion.objects.annotate(ans_count=Count('answers')).filter(ans_count__gt=0).count()
#         total_replies = Answer.objects.count() + Reply.objects.count()
#         return Response({
#             "total_discussions": total_discussions,
#             "total_answered": total_answered,
#             "total_replies": total_replies,
#         })

# class DiscussionListCreateView(generics.ListCreateAPIView):
#     permission_classes = [permissions.IsAuthenticatedOrReadOnly]
#     def get_serializer_class(self):
#         return DiscussionCreateSerializer if self.request.method == "POST" else DiscussionListSerializer

#     def get_queryset(self):
#         qs = Discussion.objects.select_related("user").order_by("-created_at")
#         search = self.request.query_params.get("search")
#         if search: qs = qs.filter(Q(title__icontains=search) | Q(body__icontains=search))
#         return qs

#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)

# class DiscussionDetailView(generics.RetrieveAPIView):
#     queryset = Discussion.objects.all()
#     serializer_class = DiscussionDetailSerializer
#     permission_classes = [permissions.AllowAny]

#     def retrieve(self, request, *args, **kwargs):
#         instance = self.get_object()
#         Discussion.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
#         instance.refresh_from_db()
#         return super().retrieve(request, *args, **kwargs)

# class AnswerCreateView(generics.CreateAPIView):
#     serializer_class = AnswerCreateSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def perform_create(self, serializer):
#         discussion = Discussion.objects.get(pk=self.kwargs.get("discussion_id"))
#         serializer.save(user=self.request.user, discussion=discussion)

# class ReplyCreateView(generics.CreateAPIView):
#     serializer_class = ReplyCreateSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def perform_create(self, serializer):
#         # ১. আইডি চেক করা (ভুল আইডি দিলে ৪০৪ এরর আসবে)
#         answer_id = self.kwargs.get("answer_id")
#         answer = get_object_or_404(Answer, pk=answer_id)
        
#         # ২. সেভ করা (আপনার মডেল অনুযায়ী 'user' ব্যবহার করুন)
#         # যদি মডেলে 'user' থাকে তবে user=self.request.user লিখুন
#         serializer.save(user=self.request.user, answer=answer)

from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import F, Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
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
    # DRF এর বিল্ট-ইন ফিল্টার এবং সার্চ ব্যবহার করা হয়েছে
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']  # UI এর বাটনগুলোর জন্য (All, General, T-TESS)
    search_fields = ['title', 'body'] # সার্চ বারের জন্য

    def get_serializer_class(self):
        return DiscussionCreateSerializer if self.request.method == "POST" else DiscussionListSerializer

    def get_queryset(self):
        # select_related ডাটাবেস কোয়েরি অপ্টিমাইজ করে
        return Discussion.objects.select_related("user").order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class DiscussionDetailView(generics.RetrieveAPIView):
    queryset = Discussion.objects.all()
    serializer_class = DiscussionDetailSerializer
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # ভিউ কাউন্ট আপডেট করার সঠিক পদ্ধতি
        Discussion.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        instance.refresh_from_db()
        return super().retrieve(request, *args, **kwargs)

class AnswerCreateView(generics.CreateAPIView):
    serializer_class = AnswerCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # get_object_or_404 ব্যবহার করা নিরাপদ
        discussion = get_object_or_404(Discussion, pk=self.kwargs.get("discussion_id"))
        serializer.save(user=self.request.user, discussion=discussion)

class ReplyCreateView(generics.CreateAPIView):
    serializer_class = ReplyCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # রিপ্লাই সেভ করার নিরাপদ পদ্ধতি
        answer = get_object_or_404(Answer, pk=self.kwargs.get("answer_id"))
        serializer.save(user=self.request.user, answer=answer)