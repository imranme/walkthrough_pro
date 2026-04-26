from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import sys
import os

# AI ডেভেলপারের মেইন লজিক ইমপোর্ট করার চেষ্টা (ডেভেলপারের ফাইলের নাম অনুযায়ী পরিবর্তন হতে পারে)
try:
    # তোমার লিস্টে 'ttes_observer' ছিল, আমি ধরে নিচ্ছি সেটার মেইন ক্লাস এটা
    from ttes_observer.main import ObserverEngine 
except ImportError:
    ObserverEngine = None

class AIProcessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_input = request.data.get('text', '')
        
        if not user_input:
            return Response({"error": "No text provided"}, status=400)

        # AI ইঞ্জিন কল করা
        if ObserverEngine:
            engine = ObserverEngine()
            # এখানে 'process' এর বদলে ডেভেলপারের দেওয়া ফাংশন নাম হবে (যেমন: run বা predict)
            ai_result = engine.process(user_input) 
            return Response({"status": "success", "data": ai_result})
        else:
            return Response({"error": "AI Engine components not found. Check your 'ai' folder."}, status=500)