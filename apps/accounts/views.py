import random
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from .serializers import RegisterSerializer, UserSerializer, ChangePasswordSerializer
from rest_framework_simplejwt.tokens import RefreshToken
# ══════════════════════════════════════════════════════════════════════════════
# 1. Auth & Profile (Login, Register, Me, Edit)
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
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

class MeView(generics.RetrieveUpdateAPIView):
    """
    Screen 6: Profile & Edit Profile.
    Retrieve (GET) profile data & Update (PATCH) personal/professional info.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ══════════════════════════════════════════════════════════════════════════════
# 2. Forget Password Logic (Screen 3, 4, 5)
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
            
            # TODO: Production-e real email send korbe
            print(f"DEBUG: OTP for {email} is {otp}") 
            
            return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)
        return Response({"error": "User with this email not found."}, status=status.HTTP_404_NOT_FOUND)

class ResetPasswordView(APIView):
    """Screen 4 & 5: Verify OTP and Set New Password"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('password')
        
        user = User.objects.filter(email=email).first()
        if user and user.profile.otp_code == otp:
            # OTP validity check (optional: for 10 mins)
            user.set_password(new_password)
            user.profile.otp_code = None # OTP use hoye gele muche fela
            user.save()
            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)
        return Response({"error": "Invalid OTP or Email."}, status=status.HTTP_400_BAD_REQUEST)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Settings (Last Screenshot)
# ══════════════════════════════════════════════════════════════════════════════

class ChangePasswordView(APIView):
    """Screen: Change Password inside Settings"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        # Password change korle token jate expire na hoy (Session update)
        update_session_auth_hash(request, user)
        return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist() # টোকেনটি ব্ল্যাকলিস্টে চলে যাবে
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

class DeleteAccountView(generics.DestroyAPIView):
    """Screen: Delete Account Button"""
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        instance.delete()