from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework import status, request
from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from .models import OTPCode
from .serializers import *
from rest_framework_simplejwt.tokens import  RefreshToken

from ..common.utils.get_client_ip import get_client_ip
from ..common.utils.otp import generate_otp
from ..common.utils.sms import send_sms


class LoginView(APIView):

    def post(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')

        user = authenticate(username=phone_number,password=password)
        if not user :
            raise serializers.ValidationError("Username or password is incorrect.")

        refresh = RefreshToken.for_user(user)

        return Response({"access": str(refresh.access_token), "refresh": str(refresh), "message": "Authenticated successfully"})



class LogoutView(APIView):
    permission_classes = [IsAuthenticated]


    def post(self, request):
        serializer = LogoutSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]
        refresh_token_string = serializer.validated_data.get("refresh_token") or request.data.get("refresh")

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



class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)



class UpdateProfileView(UpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_object(self):
        return self.request.user



class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(old_password):
            return Response(
                {"detail": "Old password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"detail": "Password updated successfully"},
            status=status.HTTP_200_OK
        )

