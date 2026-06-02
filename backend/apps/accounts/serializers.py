from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from .models import CustomUser, OTPCode
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



class ChangePhoneNumberSerializer(serializers.Serializer):
    new_phone_number = PhoneNumberField(region="IR")

    def validate_new_phone_number(self, value):
        return str(value)



class ResetPasswordSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    otp = serializers.CharField(max_length=6, write_only=True)
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):

        phone_number_obj = attrs.get('phone_number')
        phone_number_str = phone_number_obj.as_e164
        otp_input = attrs.get('otp').strip()
        new_password = attrs.get('new_password')
        new_password_confirm = attrs.get('new_password_confirm')

        if new_password != new_password_confirm:
            raise serializers.ValidationError({"new_password": "Passwords do not match"})

        try:
            user = User.objects.get(phone_number=phone_number_obj)
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone_number": "no users found with this phone number."})

        validate_password(new_password, user=user)

        cache_key_otp = f"otp:{phone_number_str}"
        cached_otp = cache.get(cache_key_otp)

        if not cached_otp:
            raise serializers.ValidationError({"otp": "OTP not valid or expired."})

        if str(cached_otp) != otp_input:
            raise serializers.ValidationError({"otp": "Wrong Code Entered"})

        attrs['user'] = user
        attrs['phone_number_str'] = phone_number_str

        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        phone_number_str = self.validated_data['phone_number_str']
        cache_key_otp = f"otp:{phone_number_str}"
        cache_key_attempts = f"otp_attempts:{phone_number_str}"

        user.set_password(self.validated_data['new_password'])
        user.save()

        cache.delete(cache_key_otp)
        cache.delete(cache_key_attempts)

        return user

