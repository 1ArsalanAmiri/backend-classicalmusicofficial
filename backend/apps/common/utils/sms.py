# apps/common/utils/sms.py
import ghasedak_sms
import os
import logging

logger = logging.getLogger(__name__)

sms_api = ghasedak_sms.Ghasedak(os.getenv('GHASEDAK_SMS_API_KEY'))


def send_sms(phone_number, code, username=None):
    if not username:
        username = "کاربر گرامی"

    try:
        newotpcommand = ghasedak_sms.SendOtpInput(
            send_date=None,
            receptors=[
                ghasedak_sms.SendOtpReceptorDto(
                    mobile=phone_number,
                )
            ],
            template_name='backend',
            inputs=[
                ghasedak_sms.SendOtpInput.OtpInput(param='Code', value=code),
            ],
            udh=False
        )

        response = sms_api.send_otp_sms(newotpcommand)

        return {"isSuccess": True, "data": response}

    except Exception as e:
        logger.error(f"Ghasedak SMS Error: {str(e)}")
        return {"isSuccess": False, "message": str(e)}
