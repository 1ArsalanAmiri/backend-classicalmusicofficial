from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["first_name" , "last_name" , "phone_number" , "date_joined" , "email" ]
        read_only_fields = [ "phone_number" ,"date_joined" ]



class LoginSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    password = serializers.CharField()



class LogoutSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    refresh = serializers.CharField()



class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match")

        validate_password(attrs["new_password"])
        return attrs
