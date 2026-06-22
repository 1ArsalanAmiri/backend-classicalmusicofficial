from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.core.cache import cache
from apps.common.serializers import SendOTPSerializer, VerifyOTPSerializer
from apps.common.utils.otp import generate_otp
from apps.common.utils.sms import send_sms
from apps.profiles.models import UserProfile


User = get_user_model()


OTP_EXPIRY_SECONDS = 300
MAX_OTP_ATTEMPTS = 3


class SendOTPView(APIView):

    serializer_class = SendOTPSerializer

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_obj = serializer.validated_data["phone_number"]
        phone_e164 = phone_obj.as_e164

        if phone_e164.startswith('+98'):
            local_phone = '0' + phone_e164[3:]
        else:
            local_phone = phone_e164

        otp = generate_otp()

        cache_key_otp = f"otp:{phone_e164}"
        cache_key_attempts = f"otp_attempts:{phone_e164}"

        try:
            sms_response = send_sms(phone_number=local_phone, code=otp)

            print(f"========== GHASEDAK RAW RESPONSE: {sms_response} ==========")

            if sms_response and sms_response.get("isSuccess") is False:
                return Response(
                    {"error": "SMS Provider Error", "details": sms_response.get("message")},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            cache.set(cache_key_otp, otp, timeout=OTP_EXPIRY_SECONDS)
            cache.set(cache_key_attempts, 0, timeout=OTP_EXPIRY_SECONDS)

        except Exception as e:
            return Response(
                {"error": "Failed to send OTP", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "message": f"OTP sent successfully. {otp}",
            "ghasedak_debug_data": sms_response
        }, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):

    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]
        otp_input = serializer.validated_data["otp"].strip()

        cache_key_otp = f"otp:{phone_number}"
        cache_key_attempts = f"otp_attempts:{phone_number}"

        try:
            cached_otp = cache.get(cache_key_otp)
            attempts = cache.get(cache_key_attempts, 0)

            if not cached_otp:
                return Response({"error": "OTP not found or expired."}, status=status.HTTP_400_BAD_REQUEST)

            if attempts >= MAX_OTP_ATTEMPTS:
                cache.delete(cache_key_otp)
                cache.delete(cache_key_attempts)
                return Response({"error": "Max attempts reached. Request a new OTP."},
                                status=status.HTTP_400_BAD_REQUEST)

            if str(cached_otp) != otp_input:

                try:
                    cache.incr(cache_key_attempts)
                except ValueError:
                    cache.set(cache_key_attempts, attempts + 1, timeout=OTP_EXPIRY_SECONDS)

                return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)


            with transaction.atomic():
                user, created = User.objects.get_or_create(phone_number=phone_number)
                UserProfile.objects.get_or_create(user=user)


            cache.delete(cache_key_otp)
            cache.delete(cache_key_attempts)


            refresh = RefreshToken.for_user(user)

            message = "User registered successfully." if created else "User Logged in successfully."
            status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

            return Response(
                {"notice": message,
                    "access": str(refresh.access_token),
                    "refresh": str(refresh)}, status=status_code)
        except Exception as e:
            return Response({"error": "An unexpected error occurred.", "details": str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


