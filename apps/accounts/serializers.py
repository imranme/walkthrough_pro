import random
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
    profile_image = serializers.ImageField(source="profile.profile_image", required=False, allow_null=True)    
    # Subscription status (Read Only)
    subscription_status = serializers.CharField(source="profile.subscription_status", read_only=True)
    is_pro = serializers.BooleanField(source="profile.is_pro", read_only=True)
    role = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)
    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name","role", "is_staff",
            "phone_number", "school_district", "specialization", 
            "years_of_experience", "profile_image", "subscription_status", "is_pro"
        )
        read_only_fields = ("id",  "email", "is_staff")

    def get_role(self, obj):
        if obj.is_superuser:
            return "super_admin"
        if obj.is_staff:
            return "admin"
        return "oveserver"


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
# 2. Registration Serializer (For Register API)     

class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model  = User
        # Username field-ti bad deya hoyeche request theke
        fields = ("id", "email", "first_name", "last_name", "phone_number", "password", "password2")

    def validate(self, attrs):
        # 1. Password match check
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        
        # 2. Email unique check
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Email is already in use."})
        
        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        
        # 3. Auto-generate Username logic
        base_username = email.split('@')
        username = base_username
        
        # Jodi username age theke thake, tobe random number add kora
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{random.randint(10, 999)}"
            counter += 1

        # 4. User Create logic (Username auto set hobe)
        user = User.objects.create_user(
            username=username, 
            email=email, 
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

        # 5. Profile update (phone number)
        phone_number = validated_data.pop('phone_number', None)
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