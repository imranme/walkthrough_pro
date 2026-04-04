from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Profile
from django.utils import timezone

# ══════════════════════════════════════════════════════════════════════════════
# 1. User & Profile Serializer (For MeView & Edit Profile)
# ══════════════════════════════════════════════════════════════════════════════

class UserSerializer(serializers.ModelSerializer):
    # Profile theke data niye asha (Read & Write both)
    phone_number = serializers.CharField(source="profile.phone_number", required=False, allow_blank=True)
    school_district = serializers.CharField(source="profile.school_district", required=False, allow_blank=True)
    specialization = serializers.CharField(source="profile.specialization", required=False, allow_blank=True)
    years_of_experience = serializers.CharField(source="profile.years_of_experience", required=False, allow_blank=True)
    profile_image = serializers.ImageField(source="profile.profile_image", read_only=True)
    
    # Subscription status (Read Only)
    subscription_status = serializers.CharField(source="profile.subscription_status", read_only=True)
    is_pro = serializers.BooleanField(source="profile.is_pro", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", 
            "phone_number", "school_district", "specialization", 
            "years_of_experience", "profile_image", "subscription_status", "is_pro"
        )
        read_only_fields = ("id", "username", "email") # Email/Username edit kora risky, tai bondho rakha bhalo

    def update(self, instance, validated_data):
        # Profile data pop kora (Nested Write)
        profile_data = validated_data.pop('profile', {})
        
        # User model update
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Profile model update
        profile = instance.profile
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance


# ══════════════════════════════════════════════════════════════════════════════
# 2. Registration Serializer (Screen 2)
# ══════════════════════════════════════════════════════════════════════════════

class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model  = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "password", "password2")

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number', None)
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""), 
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

        if phone_number:
            user.profile.phone_number = phone_number
            user.profile.save()
            
        return user


# ══════════════════════════════════════════════════════════════════════════════
# 3. Change Password Serializer (Settings Screen)
# ══════════════════════════════════════════════════════════════════════════════

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        # Django-r build-in check_password function bebohar kora hoyeche
        if not user.check_password(value):
            raise serializers.ValidationError("Puraton password-ti match korche na।")
        return value

    def validate(self, data):
        # New password matching check
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": "Notun password duti milche na।"})
        
        # New password jate old password-er moto na hoy (Optional kintu bhalo practice)
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError({"new_password": "Notun password puraton password theke alada hote hobe।"})
            
        return data