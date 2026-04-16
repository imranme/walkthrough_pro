"""
URL Configuration for Community App
Handles all endpoints related to Discussions, Answers, and Replies.
"""

from django.urls import path
from .views import (
    CommunityStatsView,
    DiscussionListCreateView,
    DiscussionDetailView,
    AnswerCreateView,
    ReplyCreateView,
)

app_name = 'community'

urlpatterns = [
    # --- Stats Cards ---
    # GET /api/community/stats/
    path("stats/", CommunityStatsView.as_view(), name="stats"),

    # --- Discussions ---
    # GET  /api/community/discussions/ -> List discussions
    # POST /api/community/discussions/ -> Create new discussion
    path("discussions/", DiscussionListCreateView.as_view(), name="discussion-list"),

    # GET  /api/community/discussions/{id}/ -> Detail & view_count increment
    path("discussions/<int:pk>/", DiscussionDetailView.as_view(), name="discussion-detail"),

    # --- Answers ---
    # POST /api/community/discussions/{discussion_id}/answers/
    path("discussions/<int:discussion_id>/answers/", AnswerCreateView.as_view(), name="answer-create"),

    # --- Replies ---
    # POST /api/community/answers/{answer_id}/replies/
    path("answers/<int:answer_id>/repli+es/", ReplyCreateView.as_view(), name="reply-create"),
]