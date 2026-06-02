from django.contrib.auth.password_validation import validate_password
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers



class SendOTPSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")



class VerifyOTPSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    otp = serializers.CharField(max_length=6)

    def validate_phone_number(self, value):
        return value.as_e164

