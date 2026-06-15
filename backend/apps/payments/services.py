# apps/payments/services.py
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ZarinpalService:

    def __init__(self):
        self.merchant_id = settings.ZP_MERCHANT_ID
        self.is_sandbox = getattr(settings, 'ZP_SANDBOX', False)

        if self.is_sandbox:
            self.base_api_url = "https://sandbox.zarinpal.com/pg/v4/payment"
            self.start_pay_url = "https://sandbox.zarinpal.com/pg/StartPay/"
        else:
            self.base_api_url = "https://api.zarinpal.com/pg/v4/payment"
            self.start_pay_url = "https://www.zarinpal.com/pg/StartPay/"

        self.headers = {
            "accept": "application/json",
            "content-type": "application/json"
        }

    def request_payment(self, amount_toman, description, callback_url, mobile=""):

        amount_rial = int(amount_toman * 10)

        url = f"{self.base_api_url}/request.json"

        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_rial,
            "description": description,
            "callback_url": callback_url,
            "metadata": {"mobile": mobile} if mobile else {}
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response_data = response.json()

            if response.status_code == 200 and not response_data.get('errors'):
                authority = response_data['data']['authority']
                gateway_url = f"{self.start_pay_url}{authority}"
                return {
                    'success': True,
                    'authority': authority,
                    'gateway_url': gateway_url,
                    'raw_response': response_data
                }
            else:
                logger.error(f"Zarinpal Request Error: HTTP {response.status_code} - {response_data}")
                return {
                    'success': False,
                    'error_message': self._get_error_message(response_data.get('errors')),
                    'raw_response': response_data
                }

        except requests.exceptions.RequestException as e:
            logger.critical(f"Zarinpal Network Error during Request: {str(e)}")
            return {'success': False, 'error_message': 'خطا در ارتباط با شبکه بانکی'}

    def verify_payment(self, amount_toman, authority):

        amount_rial = int(amount_toman * 10)

        url = f"{self.base_api_url}/verify.json"

        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_rial,
            "authority": authority
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response_data = response.json()

            if response.status_code == 200 and not response_data.get('errors'):
                data = response_data['data']
                code = data.get('code')

                if code in [100, 101]:
                    return {
                        'success': True,
                        'ref_id': data.get('ref_id'),
                        'card_pan': data.get('card_pan', ''),
                        'is_already_verified': (code == 101),
                        'raw_response': response_data
                    }
                else:
                    return {
                        'success': False,
                        'error_message': f"تراکنش ناموفق (کد: {code})",
                        'raw_response': response_data
                    }
            else:
                logger.error(f"Zarinpal Verify Error: HTTP {response.status_code} - {response_data}")
                return {
                    'success': False,
                    'error_message': self._get_error_message(response_data.get('errors')),
                    'raw_response': response_data
                }

        except requests.exceptions.RequestException as e:
            logger.critical(f"Zarinpal Network Error during Verify: {str(e)}")
            return {'success': False, 'error_message': 'خطا در ارتباط با سرور زرین‌پال'}

    def _get_error_message(self, errors_dict):
        if not errors_dict:
            return "خطای ناشناخته از سمت درگاه"

        code = errors_dict.get('code')
        message = errors_dict.get('message', 'خطای نامشخص')

        if code == -11:
            return "مرچنت کد نامعتبر است یا IP سرور در زرین‌پال ثبت نشده است."

        return f"{message} (کد: {code})"
