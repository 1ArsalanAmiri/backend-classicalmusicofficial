# apps/payments/services.py
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class AqayePardakhtService:
    def __init__(self):

        self.pin = getattr(settings, 'AQAYEPARDAKHT_PIN', '')
        self.create_url = "https://panel.aqayepardakht.ir/api/v2/create"
        self.verify_url = "https://panel.aqayepardakht.ir/api/v2/verify"
        self.start_pay_url = "https://panel.aqayepardakht.ir/startpay/"

    def request_payment(self, amount_toman, description, callback_url, mobile="", invoice_id=""):
        payload = {
            "pin": self.pin,
            "amount": amount_toman,
            "callback": callback_url,
            "description": description,
            "mobile": mobile,
            "invoice_id": invoice_id
        }

        try:
            response = requests.post(self.create_url, data=payload, timeout=10)
            response_data = response.json()

            if response_data.get('status') == "success":
                transid = response_data.get('transid')
                gateway_url = f"{self.start_pay_url}{transid}"
                return {
                    'success': True,
                    'authority': transid,
                    'gateway_url': gateway_url,
                    'raw_response': response_data
                }
            else:
                logger.error(f"AqayePardakht Request Error: {response_data}")
                return {
                    'success': False,
                    'error_message': 'خطا در ایجاد تراکنش سمت درگاه آقای پرداخت',
                    'raw_response': response_data
                }

        except requests.exceptions.RequestException as e:
            logger.critical(f"AqayePardakht Network Error during Request: {str(e)}")
            return {'success': False, 'error_message': 'خطا در ارتباط با شبکه بانکی'}

    def verify_payment(self, amount_toman, transid):
        payload = {
            "pin": self.pin,
            "amount": amount_toman,
            "transid": transid
        }

        try:
            response = requests.post(self.verify_url, data=payload, timeout=10)
            response_data = response.json()

            if response_data.get('status') == "success" and str(response_data.get('code')) == "1":
                return {
                    'success': True,
                    'ref_id': str(response_data.get('tracking_number', transid)),
                    'card_pan': response_data.get('card_number', ''),
                    'raw_response': response_data
                }
            else:
                logger.error(f"AqayePardakht Verify Error: {response_data}")
                return {
                    'success': False,
                    'error_message': "تراکنش ناموفق بود.",
                    'raw_response': response_data
                }

        except requests.exceptions.RequestException as e:
            logger.critical(f"AqayePardakht Network Error during Verify: {str(e)}")
            return {'success': False, 'error_message': 'خطا در ارتباط با سرور آقای پرداخت'}