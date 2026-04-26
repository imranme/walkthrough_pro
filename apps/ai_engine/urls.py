from django.urls import path
from .views import AIProcessView

urlpatterns = [
    path('process/', AIProcessView.as_view(), name='ai-process'),
]