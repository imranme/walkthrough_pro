import random
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from apps.accounts.models import Profile
from datetime import timedelta
from rest_framework import permissions


from .serializers import RegisterSerializer, UserSerializer, ChangePasswordSerializer

# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION (Login & Register)
# ══════════════════════════════════════════════════════════════════════════════

class RegisterView(generics.CreateAPIView):
    """
    Screen: Create Account
    Handles user registration and returns JWT tokens after successful signup.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens for the new user
        refresh = RefreshToken.for_user(user)

        return Response({
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    Screen: Email & Password Login
    Authenticates user and returns tokens with role-based redirect path.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Find user by email
        user_obj = User.objects.filter(email=email).first()

        if user_obj:
            # Authenticate using username (Django default)
            user = authenticate(username=user_obj.username, password=password)

            if user:
                refresh = RefreshToken.for_user(user)

                # Role-based routing
                if user.is_superuser or user.is_staff:
                    redirect_path = "/admin-dashboard"
                    role = "admin" if user.is_staff else "super_admin"
                else:
                    redirect_path = "/home"  # Default route for regular users
                    role = "observer"

                return Response({
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token)
                    },
                    "user": UserSerializer(user).data,
                    "role": role,
                    "redirect_to": redirect_path
                }, status=status.HTTP_200_OK)

        return Response(
            {"error": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED
        )


# ══════════════════════════════════════════════════════════════════════════════
# 2. PASSWORD RECOVERY (Forgot, Verify, Reset)
# ══════════════════════════════════════════════════════════════════════════════

class ForgotPasswordView(APIView):
    """
    Sends OTP to user's email for password reset.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()

        if user:
            # Generate 6-digit OTP
            otp = str(random.randint(100000, 999999))

            # Save OTP and creation time to user profile
            # আমরা user.profile কে সরাসরি ব্যবহার করছি
            user.profile.otp_code = otp
            user.profile.otp_created_at = timezone.now() # এই লাইনটি এখন ঠিকভাবে সেভ হবে
            user.profile.save()

            try:
                # Send OTP via email
                send_mail(
                    "Password Reset OTP",
                    f"Your OTP is: {otp}",
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
                return Response({"message": "OTP sent to your email."}, status=200)

            except Exception as e:
                return Response({"error": f"Mail error: {str(e)}"}, status=500)

        return Response({"error": "User not found."}, status=404)


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        otp_received = request.data.get('otp')

        if not otp_received:
            return Response({"error": "OTP is required."}, status=400)

        # Now 'Profile' will be recognized
        profile = Profile.objects.filter(otp_code=str(otp_received)).first()

        if profile:
            current_time = timezone.now()
            otp_time = profile.otp_created_at
            
            # 5-minute expiration check
            if current_time > otp_time + timedelta(minutes=5):
                profile.otp_code = None
                profile.save()
                return Response({"error": "OTP has expired."}, status=400)

            return Response({
                "message": "OTP verified successfully!",
                "email": profile.user.email
            }, status=200)
        
        return Response({"error": "Invalid OTP code."}, status=400)


class ResendOTPView(APIView):
    """
    Generates and sends a new OTP to the user's email.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()

        if user:
            # Generate new OTP
            new_otp = str(random.randint(100000, 999999))

            # Update OTP and timestamp
            user.profile.otp_code = new_otp
            user.profile.otp_created_at = timezone.now()
            user.profile.save()

            subject = "Your New OTP - Walkthrough Pro"
            message = (
                f"Hello,\n\n"
                f"You requested a new OTP. Your new code is: {new_otp}\n\n"
                f"Do not share this with anyone."
            )

            try:
                send_mail(
                    subject,
                    message,
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
                return Response({
                    "message": "A new OTP has been sent to your email."
                }, status=200)

            except Exception as e:
                return Response({
                    "error": f"Failed to resend email: {str(e)}"
                }, status=500)

        return Response({"error": "User not found."}, status=404)


class ResetPasswordView(APIView):
    """
    Password reset using email. 
    No login token or authorization header required.
    """
    # This allows the API to be accessed without any login token
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Get data from request body
        email = request.data.get('email')
        new_password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')

        # Validation: Check if fields are empty
        if not email or not new_password or not confirm_password:
            return Response({"error": "Email, password, and confirm password are required."}, status=400)

        # Validation: Check if passwords match
        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=400)

        # Find the user by email directly from the database
        user = User.objects.filter(email=email).first()

        if user:
            # Set the new password
            user.set_password(new_password)
            user.save()

            # Clear the OTP from profile as it's no longer needed
            user.profile.otp_code = None
            user.profile.save()

            return Response({"message": "Password reset successful!"}, status=200)
        
        # If no user matches the provided email
        return Response({"error": "User not found."}, status=404)
# ══════════════════════════════════════════════════════════════════════════════
# 3. PROFILE & SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

class MeView(generics.RetrieveUpdateAPIView):
    """
    Returns and updates the authenticated user's profile.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """
    Allows authenticated user to change password.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()

            return Response(
                {'message': 'Password changed successfully'},
                status=200
            )

        return Response(serializer.errors, status=400)


class LogoutView(APIView):
    """
    Logs out user by blacklisting refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()

            return Response(
                {"message": "Successfully logged out."},
                status=200
            )

        except Exception:
            return Response({"error": "Invalid token."}, status=400)


class DeleteAccountView(generics.DestroyAPIView):
    """
    Deletes the authenticated user's account.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ══════════════════════════════════════════════════════════════════════════════
# 4. PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

class IsSuperUser(permissions.BasePermission):
    """
    Custom permission to allow only superusers.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

    def post(self, request):
        """
        Assigns admin (staff) role to a user.
        """
        user_id = request.data.get("user_id")

        try:
            target_user = User.objects.get(id=user_id)
            target_user.is_staff = True
            target_user.save()

            return Response({
                "message": f"{target_user.email} is now set as admin."
            }, status=200)

        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)