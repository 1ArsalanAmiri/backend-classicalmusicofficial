from django.contrib.auth import authenticate
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import LogoutSerializer, ChangePhoneNumberSerializer, ResetPasswordSerializer, \
    DeleteAccountSerializer, LoginSerializer, VerifyDeleteAccountSerializer
from .models import CustomUser
import uuid
import time
from django.core.cache import cache
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken



OTP_EXPIRY_SECONDS = 300
MAX_OTP_ATTEMPTS = 3



class LoginView(APIView):

    serializer_class = LoginSerializer

    def post(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')

        user = authenticate(request, phone_number=phone_number, password=password)
        if not user :
            raise serializers.ValidationError("Username or password is incorrect.")

        refresh = RefreshToken.for_user(user)

        return Response({"access": str(refresh.access_token), "refresh": str(refresh), "message": "Authenticated successfully"})



class LogoutView(APIView):

    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]


    def post(self, request):
        serializer = LogoutSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]
        refresh_token_string = serializer.validated_data.get("refresh")

        if not refresh_token_string:
            return Response({"error": "Refresh Token is Required"}, status=status.HTTP_400_BAD_REQUEST)

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token_string)

            if str(token['user_id']) != str(request.user.id):
                return Response({"error": "You Dont Have Permission For This Operation."}, status=status.HTTP_403_FORBIDDEN)

            token.blacklist()

            return Response({"message": "Logout Success, Blacklisted Token. "},status=status.HTTP_205_RESET_CONTENT)

        except TokenError:
            return Response({"error": "Refresh Token Invalid Or Used."},status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": "Internal Server Error While Logging out. Please Try Again..."},status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ResetPasswordView(APIView):

    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        return Response({"message": "Password has been reset successfully."},status=status.HTTP_200_OK)



class DeleteAccountView(APIView):

    serializer_class = DeleteAccountSerializer
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        refresh_token_string = serializer.validated_data['refresh']

        try:
            token = RefreshToken(refresh_token_string)
            token.blacklist()
        except TokenError:
            pass

        user.is_active = False

        fake_identifier = str(uuid.uuid4())[:8]
        user.phone_number = f"+98000{fake_identifier}"
        user.first_name = "Deleted"
        user.last_name = "User"
        user.email = ""
        user.username = None

        user.save()

        return Response(
            {"message": "حساب کاربری شما با موفقیت غیرفعال و حذف شد."},
            status=status.HTTP_204_NO_CONTENT
        )



class VerifyDeleteAccountView(APIView):

    serializer_class = VerifyDeleteAccountSerializer
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        otp_input = request.data.get("otp")
        refresh_token = request.data.get("refresh")

        if not otp_input or not refresh_token:
            return Response(
                {"error": "فیلدهای otp و refresh الزامی هستند."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp_input = str(otp_input).strip()

        phone_number = str(request.user.phone_number)

        cache_key_otp = f"otp:{phone_number}"
        cache_key_attempts = f"otp_attempts:{phone_number}"

        try:
            cached_otp = cache.get(cache_key_otp)
            attempts = cache.get(cache_key_attempts, 0)

            if not cached_otp:
                return Response(
                    {"error": "OTP not found or expired."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if attempts >= MAX_OTP_ATTEMPTS:
                cache.delete(cache_key_otp)
                cache.delete(cache_key_attempts)
                return Response(
                    {"error": "Max attempts reached. Request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if str(cached_otp) != otp_input:
                try:
                    cache.incr(cache_key_attempts)
                except ValueError:
                    cache.set(cache_key_attempts, attempts + 1, timeout=OTP_EXPIRY_SECONDS)

                return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)


            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                return Response(
                    {"error": "توکن نامعتبر است یا قبلاً منقضی شده است."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = request.user
            user.is_active = False
            fake_identifier = str(int(time.time()))[-7:]
            user.phone_number = f"+98000{fake_identifier}"
            user.first_name = ""
            user.last_name = ""
            user.save()

            cache.delete(cache_key_otp)
            cache.delete(cache_key_attempts)

            return Response(
                {"notice": "حساب کاربری شما با موفقیت حذف شد."},
                status=status.HTTP_204_NO_CONTENT
            )

        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )