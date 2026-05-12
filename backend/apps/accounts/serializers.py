from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["username" , "first_name" , "last_name" , "phone_number" , "date_joined" , "email"]


class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ["username", "phone_number", "password", "confirm_password"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("رمزها یکسان نیستند")
        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        user = CustomUser.objects.create_user(username=validated_data["username"],phone_number=validated_data["phone_number"],password=validated_data["password"])
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data["username"],password=data["password"])
        if not user:
            raise serializers.ValidationError("اطلاعات ورود اشتباه است")
        refresh = RefreshToken.for_user(user)
        return {"user": user,"refresh": str(refresh),"access": str(refresh.access_token)}



