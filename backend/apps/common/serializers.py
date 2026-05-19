from django.contrib.auth.password_validation import validate_password
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers



class SendOTPSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    purpose = serializers.ChoiceField(choices=["LOGIN", "RESET_PASSWORD" , "REGISTER", "CHANGE_PHONE"])



class VerifyOTPSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    otp = serializers.CharField(max_length=6)
    purpose = serializers.ChoiceField(choices=["LOGIN", "RESET_PASSWORD", "REGISTER", "CHANGE_PHONE"])

    def validate_phone_number(self, value):
        return value.as_e164

    def validate_purpose(self, value):
        return value.upper()



class ResetPasswordSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)
    purpose = serializers.ChoiceField(choices=["RESET_PASSWORD"])

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Passwords do not match")

        validate_password(attrs["new_password"])
        return attrs



class ChangePhoneNumberSerializer(serializers.Serializer):
    new_phone_number = PhoneNumberField(region="IR")

    def validate_new_phone_number(self, value):
        return str(value)

