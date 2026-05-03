from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from random import randint
from .tasks import send_sms_task, send_email_task
from pay.models import PayInquiry, PayRequest
from pay.zarinpal.zarinpal import ZarinPal
from pay.zarinpal.utils.Config import Config



class PasswordResetViewSet(viewsets.ModelViewSet):

    @action(detail=False, methods=['post'], url_path='send-code')
    def send_reset_code(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({'error': 'شماره تلفن الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        code = str(random.randint(100000, 999999))

        reset_key = f'reset_code_{phone_number}'
        cache.set(reset_key, {
            'code': code,
            'time': timezone.now().isoformat()
        }, timeout=600)

        from .tasks import send_sms_task, send_email_task
        send_sms_task.delay(phone_number, code)

        return Response({
            'message': 'کد بازنشانی ارسال شد',
            'expires_in': '10 دقیقه'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-code')
    def verify_code(self, request):
        phone_number = request.data.get('phone_number')
        code = request.data.get('code')

        if not all([phone_number, code]):
            return Response({'error': 'شماره تلفن و کد الزامی هستند'}, status=status.HTTP_400_BAD_REQUEST)

        reset_key = f'reset_code_{phone_number}'
        reset_data = cache.get(reset_key)

        if not reset_data:
            return Response({'error': 'کد منقضی شده یا یافت نشد'}, status=status.HTTP_400_BAD_REQUEST)

        code_time = timezone.datetime.fromisoformat(reset_data['time'])
        if timezone.now() - code_time > timedelta(minutes=10):
            cache.delete(reset_key)
            return Response({'error': 'کد منقضی شده است'}, status=status.HTTP_400_BAD_REQUEST)

        if reset_data['code'] != code:
            return Response({'error': 'کد نادرست است'}, status=status.HTTP_400_BAD_REQUEST)

        import secrets
        reset_token = secrets.token_urlsafe(32)

        token_key = f'reset_token_{phone_number}'
        cache.set(token_key, reset_token, timeout=300)
        cache.delete(reset_key)

        return Response({
            'message': 'کد تایید شد',
            'reset_token': reset_token
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reset-password')
    def reset_password(self, request):
        phone_number = request.data.get('phone_number')
        reset_token = request.data.get('reset_token')
        new_password = request.data.get('new_password')

        if not all([phone_number, reset_token, new_password]):
            return Response({'error': 'تمام فیلدها الزامی هستند'}, status=status.HTTP_400_BAD_REQUEST)

        token_key = f'reset_token_{phone_number}'
        stored_token = cache.get(token_key)

        if not stored_token or stored_token != reset_token:
            return Response({'error': 'توکن نامعتبر یا منقضی شده است'}, status=status.HTTP_400_BAD_REQUEST)

        from .models import CustomUser

        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            user.set_password(new_password)
            user.save()

            cache.delete(token_key)

            return Response({'message': 'رمز عبور با موفقیت تغییر کرد'}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({'error': 'کاربر یافت نشد'}, status=status.HTTP_404_NOT_FOUND)




class RegistrationViewSet(viewsets.ModelViewSet):

    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        username = request.data.get('username')
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')
        confirm_password = request.data.get('confirmPassword')

        if not all([username, phone_number, password, confirm_password]):
            return Response({'error': 'تمام فیلدها الزامی هستند'}, status=status.HTTP_400_BAD_REQUEST)

        if password != confirm_password:
            return Response({'error': 'رمزهای عبور مطابقت ندارند'}, status=status.HTTP_400_BAD_REQUEST)

        from .models import CustomUser

        if CustomUser.objects.filter(username=username).exists():
            return Response({'error': 'این نام کاربری قبلاً استفاده شده است'}, status=status.HTTP_400_BAD_REQUEST)

        if CustomUser.objects.filter(phone_number=phone_number).exists():
            return Response({'error': 'این شماره تلفن قبلاً استفاده شده است'}, status=status.HTTP_400_BAD_REQUEST)

        last_attempt_key = f'last_sms_attempt_{phone_number}'
        last_attempt = cache.get(last_attempt_key)

        if last_attempt:
            last_attempt_time = timezone.datetime.fromisoformat(last_attempt)
            if timezone.now() - last_attempt_time < timedelta(minutes=2):
                remaining = 120 - int((timezone.now() - last_attempt_time).total_seconds())
                return Response({'error': f'لطفاً {remaining} ثانیه صبر کنید قبل از درخواست کد جدید'},
                                status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            code = str(randint(100000, 999999))

            pending_reg_key = f'pending_registration_{phone_number}'
            cache.set(pending_reg_key, {
                'username': username,
                'phone_number': phone_number,
                'password': password
            }, timeout=600)

            verification_key = f'pending_verification_{phone_number}'
            cache.set(verification_key, {
                'code': code,
                'time': timezone.now().isoformat()
            }, timeout=600)

            cache.set(last_attempt_key, timezone.now().isoformat(), timeout=120)

            from .tasks import send_ghasedak_sms_task
            send_ghasedak_sms_task.delay(phone_number, code, username)

            return Response({
                'message': 'کد تایید به شماره تلفن شما ارسال شد',
                'phone_number': phone_number,
                'expires_in': '10 دقیقه'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'خطا در ارسال کد تایید: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def send_reset_code(self, request):

        phone_number = request.data.get('phone_number')
        email = request.data.get('email')

        if not phone_number and not email:
            return Response({'error': 'شماره موبایل یا ایمیل الزامی است'},status=status.HTTP_400_BAD_REQUEST)

        try:
            reset_code = str(randint(100000, 999999))
            current_time = timezone.now().isoformat()

            cache_key = f'reset_code_{phone_number or email}'
            cache_data = {
                'code': reset_code,
                'time': current_time,
                'phone_number': phone_number,
                'email': email
            }
            cache.set(cache_key, cache_data, timeout=600)  # 10 minutes

            if phone_number:
                send_sms_task.delay(phone_number, reset_code)

            if email:
                send_email_task.delay(email, reset_code)

            return Response({'message': 'کد بازنشانی ارسال شد','expires_in': '10 دقیقه'},status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'خطا در ارسال کد: {str(e)}'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def verify_code(self, request):
        entered_code = request.data.get('reset_code')
        phone_number = request.data.get('phone_number')
        email = request.data.get('email')

        if not entered_code:
            return Response({'error': 'کد الزامی است'},status=status.HTTP_400_BAD_REQUEST)

        if not phone_number and not email:
            return Response({'error': 'شماره موبایل یا ایمیل الزامی است'},status=status.HTTP_400_BAD_REQUEST)

        cache_key = f'reset_code_{phone_number or email}'
        stored_data = cache.get(cache_key)

        if not stored_data:
            return Response({'error': 'کد منقضی شده یا یافت نشد. لطفاً دوباره درخواست کنید'},status=status.HTTP_400_BAD_REQUEST)

        stored_code = stored_data.get('code')
        code_time = stored_data.get('time')

        try:
            from datetime import datetime
            sent_time = datetime.fromisoformat(code_time)
            current_time = timezone.now()


            if (current_time - sent_time) >= timedelta(minutes=10):
                cache.delete(cache_key)
                return Response({'error': 'کد منقضی شده است'},status=status.HTTP_400_BAD_REQUEST)


            if entered_code != stored_code:
                return Response({'error': 'کد وارد شده نامعتبر است'},status=status.HTTP_400_BAD_REQUEST)

            reset_token = str(randint(100000000, 999999999))
            token_key = f'reset_token_{phone_number or email}'
            cache.set(token_key, reset_token, timeout=300)  # 5 minutes

            cache.delete(cache_key)

            return Response({'message': 'کد تأیید شد','reset_token': reset_token},status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'خطا در پردازش: {str(e)}'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


