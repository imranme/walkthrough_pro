import random
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer, ChangePasswordSerializer

# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION (Login & Register)
# ══════════════════════════════════════════════════════════════════════════════

class RegisterView(generics.CreateAPIView):
    """Screen 2: Create Account"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    """Screen 1: Email & Password Login"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Email diye user khunje ber kora
        user_obj = User.objects.filter(email=email).first()
        if user_obj:
            user = authenticate(username=user_obj.username, password=password)
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
                    "user": UserSerializer(user).data
                }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

# ══════════════════════════════════════════════════════════════════════════════
# 2. PASSWORD RECOVERY (Forgot & Reset)
# ══════════════════════════════════════════════════════════════════════════════

class ForgotPasswordView(APIView):
    """Screen 3: Send OTP to Email"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        if user:
            otp = str(random.randint(100000, 999999))
            user.profile.otp_code = otp
            user.profile.otp_created_at = timezone.now()
            user.profile.save()
            
            print(f"DEBUG OTP: {otp}") # Production-e Email backend use korbe
            return Response({"message": "OTP sent successfully."}, status=200)
        return Response({"error": "User not found."}, status=404)

class ResetPasswordView(APIView):
    """Screen 4 & 5: Verify OTP and Set New Password"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')
        
        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=400)

        user = User.objects.filter(email=email).first()
        # String comparison nishchit kora
        if user and str(user.profile.otp_code) == str(otp):
            user.set_password(new_password)
            user.save()
            user.profile.otp_code = None
            user.profile.save()
            return Response({"message": "Password reset successful."}, status=200)
        
        return Response({"error": "Invalid OTP or Email."}, status=400)

# ══════════════════════════════════════════════════════════════════════════════
# 3. PROFILE & SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

class MeView(generics.RetrieveUpdateAPIView):
    """Screen 6: Profile View & Edit"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    """Settings: Change Password"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()
            return Response({'message': 'Password changed successfully'}, status=200)
        return Response(serializer.errors, status=400)

class LogoutView(APIView):
    """Settings: Logout"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist() 
            return Response({"message": "Successfully logged out."}, status=200)
        except Exception:
            return Response({"error": "Invalid token."}, status=400)

class DeleteAccountView(generics.DestroyAPIView):
    """Settings: Delete Account"""
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user