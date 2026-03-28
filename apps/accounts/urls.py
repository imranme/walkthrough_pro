from django.urls import path
# SimpleJWT er built-in views (Ekhane LogoutView nei)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Tomar nijer toiri kora views (Ekhan theke LogoutView import hobe)
from .views import (
    RegisterView, 
    MeView, 
    ForgotPasswordView, 
    ResetPasswordView, 
    ChangePasswordView, 
    DeleteAccountView,
    LogoutView  # << Eita ekhane thakbe
)

urlpatterns = [
    # Auth
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"), # Ekhon eita kaj korbe

    # Profile & Settings
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("delete-account/", DeleteAccountView.as_view(), name="delete-account"),

    # Password Recovery
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]