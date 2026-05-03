from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_sms_task(self, phone_number, reset_code):

    try:
        # sms_service.send(phone_number, f'کد بازنشانی: {reset_code}')

        logger.info(f"SMS sent to {phone_number}: {reset_code}")
        print(f"[SMS] {phone_number} -> Code: {reset_code}")

        return {'status': 'success', 'phone': phone_number}

    except Exception as e:
        logger.error(f"SMS failed for {phone_number}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_email_task(self, email, reset_code):
    try:
        from django.core.mail import send_mail
        from django.conf import settings

        subject = 'کد بازنشانی رمز عبور'
        message = f'کد بازنشانی شما: {reset_code}\n\nاین کد تا 10 دقیقه معتبر است.'

        send_mail(subject,message,settings.DEFAULT_FROM_EMAIL,[email],fail_silently=False,)

        logger.info(f"Email sent to {email}: {reset_code}")
        print(f"[EMAIL] {email} -> Code: {reset_code}")

        return {'status': 'success', 'email': email}

    except Exception as e:
        logger.error(f"Email failed for {email}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_ghasedak_sms_task(self, phone_number, code, username=None):
    try:
        import ghasedak_sms
        from django.conf import settings

        sms_api = ghasedak_sms.Api(settings.GHASEDAK_API_KEY)

        inputs = [
            ghasedak_sms.SendOtpInput.OtpInput(param='code', value=code),
        ]

        if username:
            inputs.append(ghasedak_sms.SendOtpInput.OtpInput(
                param='name', value=username))

        newotpcommand = ghasedak_sms.SendOtpInput(send_date=None,receptors=[ghasedak_sms.SendOtpReceptorDto(mobile=phone_number)],template_name='OTP',inputs=inputs,udh=False)
        response = sms_api.send_otp_sms(newotpcommand)

        logger.info(f"Ghasedak SMS sent to {phone_number}: {code}")
        return {'status': 'success', 'phone': phone_number}

    except Exception as e:
        logger.error(f"Ghasedak SMS failed for {phone_number}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

