from django.core.cache import cache
from django.core.validators import RegexValidator
from django.utils import timezone
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
import jdatetime
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.utils.translation import gettext_lazy as _


User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):

    date_joined_jalali = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'phone_number', 'username', 'date_joined', 'date_joined_jalali']

    def get_date_joined_jalali(self, obj):
        if not obj.date_joined:
            return None

        local_time = timezone.localtime(obj.date_joined)
        jalali_date = jdatetime.datetime.fromgregorian(datetime=local_time)
        return jalali_date.strftime("%Y/%m/%d")



class LoginSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(region="IR")
    password = serializers.CharField()



class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)



class RequestChangePhoneSerializer(serializers.Serializer):
    new_phone_number = serializers.CharField(
        max_length=13,
        validators=[RegexValidator(regex=r'^\+989\d{9}$', message="فرمت شماره موبایل نامعتبر است. (مثال: 989120000000+)")],
        help_text="شماره موبایل جدید کاربر"
    )



class VerifyChangePhoneSerializer(serializers.Serializer):
    new_phone_number = serializers.CharField(max_length=13)
    otp = serializers.CharField(max_length=5, min_length=4)



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



class VerifyDeleteAccountSerializer(serializers.Serializer):
    otp = serializers.CharField(
        max_length=6,
        required=True,
        help_text=_("کد تایید ارسال شده به شماره موبایل")
    )
    refresh = serializers.CharField(
        required=True,
        help_text=_("توکن Refresh برای باطل کردن نشست فعلی")
    )

    def validate_refresh(self, value):
        try:
            RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError(_("توکن نامعتبر است یا قبلاً منقضی شده است."))
        return value



class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    refresh = serializers.CharField(write_only=True, required=True, help_text="توکن رفرش برای خروج کامل کاربر")

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("رمز عبور وارد شده اشتباه است.")
        return value
