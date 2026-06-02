from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import *
from rest_framework_simplejwt.tokens import  RefreshToken



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



class ChangePhoneNumberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePhoneNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_phone_number = serializer.validated_data["new_phone_number"]

        if User.objects.filter(phone_number=new_phone_number).exists():
            return Response({"error": "Phone number already used"}, status=400)

        user.phone_number = new_phone_number
        user.save(update_fields=["phone_number"])

        return Response({"detail": "Phone number changed"}, status=200)



class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        return Response({"message": "Password has been reset successfully."},status=status.HTTP_200_OK)