import uuid
import random
from django.contrib.auth import authenticate
from django.core.cache import cache
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    ResetPasswordSerializer,
    LoginSerializer,
    VerifyDeleteAccountSerializer
)

OTP_EXPIRY_SECONDS = 300
MAX_OTP_ATTEMPTS = 3


class LoginView(APIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data.get('phone_number')
        password = serializer.validated_data.get('password')

        user = authenticate(request, phone_number=phone_number, password=password)
        if not user:
            return Response(
                {"error": "شماره تلفن یا رمز عبور اشتباه است."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)

        response = Response({
            "access": str(refresh.access_token),
            "message": "ورود با موفقیت انجام شد."
        }, status=status.HTTP_200_OK)

        # FIX: SameSite='Lax' -> 'None'
        # چون فرانت روی یک origin دیگر (cross-site) اجرا می‌شود و این کوکی باید
        # روی درخواست‌های fetch/axios با withCredentials=true ارسال شود، نه فقط
        # روی navigation مستقیم top-level. SameSite=None اجباراً باید با Secure=True
        # همراه باشد که از قبل تنظیم بود.
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            samesite='None',
            secure=True,
        )

        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token_string = request.COOKIES.get('refresh_token')

        if not refresh_token_string:
            return Response(
                {"error": "توکن رفرش در کوکی یافت نشد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token_string)

            if str(token['user_id']) != str(request.user.id):
                return Response(
                    {"error": "شما اجازه انجام این عملیات را ندارید."},
                    status=status.HTTP_403_FORBIDDEN
                )

            token.blacklist()

            response = Response(
                {"message": "خروج با موفقیت انجام شد."},
                status=status.HTTP_200_OK
            )

            response.delete_cookie(
                key='refresh_token',
                samesite='None',
            )

            return response

        except TokenError:
            return Response(
                {"error": "توکن رفرش نامعتبر است یا قبلاً استفاده شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            return Response(
                {"error": "خطای داخلی سرور در هنگام خروج. لطفاً دوباره تلاش کنید."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResetPasswordView(APIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "رمز عبور با موفقیت تغییر یافت."},
            status=status.HTTP_200_OK
        )


class RequestDeleteAccountOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        phone_number = str(request.user.phone_number)
        otp = str(random.randint(100000, 999999))

        cache_key_otp = f"otp:{phone_number}"
        cache_key_attempts = f"otp_attempts:{phone_number}"

        cache.set(cache_key_otp, otp, timeout=OTP_EXPIRY_SECONDS)
        cache.delete(cache_key_attempts)

        # TODO: فراخوانی وب‌سرویس پیامک برای ارسال otp به کاربر

        return Response(
            {"message": "کد تایید برای حذف حساب ارسال شد."},
            status=status.HTTP_200_OK
        )


class VerifyDeleteAccountView(APIView):
    serializer_class = VerifyDeleteAccountSerializer
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = VerifyDeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp_input = str(serializer.validated_data.get("otp")).strip()
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {"error": "توکن رفرش در کوکی یافت نشد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = str(request.user.phone_number)
        cache_key_otp = f"otp:{phone_number}"
        cache_key_attempts = f"otp_attempts:{phone_number}"

        try:
            cached_otp = cache.get(cache_key_otp)
            attempts = cache.get(cache_key_attempts, 0)

            if not cached_otp:
                return Response(
                    {"error": "کد تایید یافت نشد یا منقضی شده است."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if attempts >= MAX_OTP_ATTEMPTS:
                cache.delete(cache_key_otp)
                cache.delete(cache_key_attempts)
                return Response(
                    {"error": "تعداد تلاش‌های ناموفق بیش از حد مجاز است. مجدداً کد جدید دریافت کنید."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if str(cached_otp) != otp_input:
                try:
                    cache.incr(cache_key_attempts)
                except ValueError:
                    cache.set(cache_key_attempts, attempts + 1, timeout=OTP_EXPIRY_SECONDS)

                return Response({"error": "کد تایید اشتباه است."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass

            user = request.user
            user.is_active = False

            fake_identifier = str(uuid.uuid4())[:8]
            user.phone_number = f"+98000{fake_identifier}"
            user.first_name = "Deleted"
            user.last_name = "User"
            user.email = ""
            user.username = None
            user.save()

            cache.delete(cache_key_otp)
            cache.delete(cache_key_attempts)

            response = Response(
                {"message": "حساب کاربری شما با موفقیت غیرفعال و حذف شد."},
                status=status.HTTP_200_OK
            )
            response.delete_cookie('refresh_token', samesite='None')
            return response

        except Exception:
            return Response(
                {"error": "خطایی در پردازش درخواست رخ داد. لطفاً دوباره تلاش کنید."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            refresh_token = response.data.get('refresh')

            if 'refresh' in response.data:
                del response.data['refresh']

            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                max_age=30 * 24 * 60 * 60,
                httponly=True,
                samesite='None',
                secure=True,
            )
        return response


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {"detail": "توکن رفرش در کوکی یافت نشد."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        data = request.data.copy()
        data['refresh'] = refresh_token

        serializer = self.get_serializer(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        response_data = serializer.validated_data
        response = Response(response_data, status=status.HTTP_200_OK)

        if 'refresh' in response_data:
            new_refresh = response_data['refresh']
            del response.data['refresh']

            response.set_cookie(
                key='refresh_token',
                value=new_refresh,
                max_age=30 * 24 * 60 * 60,
                httponly=True,
                samesite='None',
                secure=True,
            )
        return response