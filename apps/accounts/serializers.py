from django.contrib.auth.models import User
from rest_framework import serializers
from django.utils import timezone  # << Nischit koro eita import hoyeche

class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ("id", "username", "email", "first_name", "last_name", "password", "password2")

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        # Ekhane 'create_user' ke bolar dorkar nai amra last_login dichchi
        # Django automatic set korbe, amra shudhu basic fields pathabo
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""), 
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        
        # Manual Force Save (Jodi database ekhono error dey)
        user.last_login = timezone.now()
        user.save()
        
        return user

class UserSerializer(serializers.ModelSerializer):
    subscription_status = serializers.CharField(source="profile.subscription_status", read_only=True)
    is_pro = serializers.BooleanField(source="profile.is_pro", read_only=True)

    class Meta:
        model  = User
        fields = ("id", "username", "email", "subscription_status", "is_pro")