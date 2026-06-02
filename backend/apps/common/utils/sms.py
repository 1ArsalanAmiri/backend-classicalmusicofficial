import ghasedak_sms
import os

from rest_framework.response import Response

sms_api = ghasedak_sms.Ghasedak(os.getenv('GHASEDAK_SMS_API_KEY'))


def send_sms(phone_number, code , username=None):
        try:
            newotpcommand = ghasedak_sms.SendOtpInput(
                send_date=None,
                receptors=[
                    ghasedak_sms.SendOtpReceptorDto(
                        mobile='phone_number',
                    )
                ],
                template_name='newOTP',
                inputs=[
                    ghasedak_sms.SendOtpInput.OtpInput(param='Code', value='code'),
                    ghasedak_sms.SendOtpInput.OtpInput(param='Name', value='username'),
                ],
                udh=False
            )
            response = sms_api.send_otp_sms(newotpcommand)
            print(response)

            return Response(response)

        except Exception as e:

            return False
