from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.common.serializers import *
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import  RefreshToken
from apps.common.utils.otp import generate_otp
from apps.common.utils.sms import send_sms
from apps.common.utils.get_client_ip import get_client_ip
from apps.accounts.models import OTPCode, CustomUser

User = get_user_model()


class SendOTPView(APIView):

    def post(self, request):

        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"].as_e164
        purpose = serializer.validated_data["purpose"].upper()
        PURPOSE_CHOICES = ["LOGIN" , "REGISTER" , "RESET_PASSWORD" , "CHANGE_PHONE"]
        user_exists = CustomUser.objects.filter(phone_number=phone_number).exists()

        if purpose not in PURPOSE_CHOICES:
            return Response({"error": "Invalid purpose"}, status=400)

        if not user_exists:
            return Response({"error": "User not found"}, status=404)


        with transaction.atomic():
            OTPCode.objects.filter(phone_number=phone_number,purpose=purpose,is_used=False).update(is_used=True)

            expires_at = timezone.now() + timedelta(minutes=5)

            otp = generate_otp()

            OTPCode.objects.create(phone_number=phone_number,code=otp,purpose=purpose,expires_at=expires_at,is_used=False)

        try:
            send_sms(phone_number, otp)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"error": "Failed to send OTP"}, status=500)

        print(phone_number , type(phone_number))
        print(otp , type(otp))

        return Response({"message": f"OTP sent successfully => {otp}"})




class VerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        otp_input = serializer.validated_data["otp"].strip()
        purpose = serializer.validated_data["purpose"]
        max_attempts = 3

        with transaction.atomic():
            otp_obj = OTPCode.objects.select_for_update().filter(
                phone_number=str(phone_number),
                purpose=purpose,
                is_used=False
            ).order_by("-created_at").first()

            if not otp_obj:
                return Response({"error": "OTP not found or expired"}, status=400)

            # Expired
            if timezone.now() > otp_obj.expires_at:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])
                return Response({"error": "OTP expired"}, status=400)

            # Attempts exceeded
            if otp_obj.attempts >= max_attempts:
                otp_obj.is_used = True
                otp_obj.save(update_fields=["is_used"])
                return Response({"error": "Too many attempts"}, status=400)

            # Wrong code
            if otp_obj.code.strip() != otp_input:
                otp_obj.attempts += 1
                otp_obj.save(update_fields=["attempts"])
                return Response({"error": "Invalid OTP"}, status=400)

            # Success
            otp_obj.is_used = True
            otp_obj.save(update_fields=["is_used"])

        #PURPOSE LOGIC
        if purpose == "REGISTER":
            user, _ = User.objects.get_or_create(phone_number=phone_number)
            refresh = RefreshToken.for_user(user)
            return Response({"access": str(refresh.access_token), "refresh": str(refresh)}, status=200)

        elif purpose == "LOGIN":
            try:
                user = User.objects.get(phone_number=phone_number)
                refresh = RefreshToken.for_user(user)
                return Response({"access": str(refresh.access_token), "refresh": str(refresh)}, status=200)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)

        elif purpose == "RESET_PASSWORD":
            reset_serializer = ResetPasswordSerializer(data=request.data)
            reset_serializer.is_valid(raise_exception=True)
            password = reset_serializer.validated_data["new_password"]

            try:
                user = User.objects.get(phone_number=phone_number)
                user.set_password(password)
                user.save()
                return Response({"detail": "Password reset successful"}, status=200)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)

        elif purpose == "CHANGE_PHONE":
            change_serializer = ChangePhoneNumberSerializer(
                data={"phone_number": phone_number,"new_phone_number": request.data.get("new_phone_number")}
            )
            change_serializer.is_valid(raise_exception=True)

            new_phone_number = change_serializer.validated_data["new_phone_number"]

            if User.objects.filter(phone_number=new_phone_number).exists():
                return Response({"error": "Phone number already used"}, status=400)

            user = User.objects.get(phone_number=phone_number)
            user.phone_number = new_phone_number
            user.save(update_fields=["phone_number"])

            return Response({"detail": "Phone number changed"}, status=200)

        return Response({"message": "OTP verified"}, status=200)
