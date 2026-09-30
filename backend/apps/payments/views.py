# apps/payments/views.py
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Payment, PaymentStatus, Discount, DiscountUsage
from .services import AqayePardakhtService
from apps.subscriptions.models import Subscription


def _get_frontend_url() -> str:
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://clmusic.ir')
    return str(frontend_url).rstrip('/')


def _cancel_redirect(reason: str):
    base_url = _get_frontend_url()
    return redirect(f"{base_url}/payments/cancel?reason={quote(str(reason))}")


def _verify_redirect(ref_id: str):
    base_url = _get_frontend_url()
    return redirect(f"{base_url}/payments/verify?ref_id={quote(str(ref_id))}")


class PaymentRequestSerializer(serializers.Serializer):
    subscription_id = serializers.IntegerField(required=True, help_text="شناسه اشتراک")
    discount_code = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, help_text="کد تخفیف"
    )


class PaymentRequestAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription_id = serializer.validated_data.get('subscription_id')
        discount_code = serializer.validated_data.get('discount_code')
        user = request.user

        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return Response({"error": "اشتراک یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        base_price = (
            subscription.discounted_price
            if subscription.has_permanent_discount
            else subscription.price
        )

        final_amount = base_price
        discount_obj = None

        if discount_code:
            try:
                discount_obj = Discount.objects.get(code=discount_code, is_active=True)
                is_valid, msg = discount_obj.is_valid_for_use(user, subscription)

                if not is_valid:
                    return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

                discount_amount = discount_obj.calculate_discount_amount(base_price)
                # اطمینان از اینکه مبلغ نهایی در صورت خطای محاسباتی تخفیف، منفی نمی‌شود
                final_amount = max(0, base_price - discount_amount)

            except Discount.DoesNotExist:
                return Response({"error": "کد تخفیف نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        mobile = getattr(user, 'phone_number', '') or ''

        # قرار دادن ثبت دیتابیس در تراکنش تا در صورت خطا، دیتای ناقص ثبت نشود
        with transaction.atomic():
            payment = Payment.objects.create(
                user=user,
                subscription=subscription,
                discount=discount_obj,
                amount=final_amount,
                status=PaymentStatus.PENDING,
                mobile=str(mobile),
                description=f"خرید اشتراک {subscription.name} برای {user.username}"
            )

            # پردازش پرداخت‌های رایگان (تخفیف ۱۰۰ درصدی)
            if final_amount <= 0:
                payment.status = PaymentStatus.SUCCESS
                payment.verified_at = timezone.now()
                payment.save(update_fields=['status', 'verified_at'])

                from apps.profiles.models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=payment.user)
                profile.subscribe(subscription)

                if discount_obj:
                    DiscountUsage.objects.create(discount=discount_obj, user=user)
                    # استفاده از F برای جلوگیری از Race Condition هنگام آپدیت تعداد استفاده
                    discount_obj.current_uses = F('current_uses') + 1
                    discount_obj.save(update_fields=['current_uses'])

                return Response(
                    {"message": "اشتراک شما به صورت رایگان فعال شد.", "is_free": True},
                    status=status.HTTP_200_OK
                )

        # درخواست به درگاه (این بخش به عمد خارج از transaction قرار گرفته است)
        payment_domain = getattr(settings, 'PAYMENT_DOMAIN', 'https://clmusic.ir').rstrip('/')
        callback_url = f"{payment_domain}{reverse('payments:verify')}"

        aqaye_service = AqayePardakhtService()
        api_response = aqaye_service.request_payment(
            amount_toman=int(payment.amount),
            description=payment.description,
            callback_url=callback_url,
            mobile=str(mobile),
            invoice_id=str(payment.id)
        )

        payment.raw_request = api_response
        payment.save(update_fields=['raw_request'])

        if api_response.get("success"):
            payment.authority = api_response["authority"]
            payment.save(update_fields=['authority'])
            return Response({"gateway_url": api_response["gateway_url"]}, status=status.HTTP_200_OK)
        else:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=['status'])
            return Response(
                {"error": api_response.get("error_message", "خطا در اتصال به درگاه")},
                status=status.HTTP_502_BAD_GATEWAY
            )


class PaymentVerifyAPIView(APIView):
    permission_classes = []

    def _get_param(self, request, *names):
        params = request.query_params if request.method == 'GET' else request.data
        lower_map = {str(k).lower(): v for k, v in params.items()}
        for name in names:
            if name in params:
                return params.get(name)
            if name.lower() in lower_map:
                return lower_map[name.lower()]
        return None

    def _handle_callback(self, request):
        authority = self._get_param(request, 'transid', 'trans_id', 'TransId', 'Authority', 'authority')
        payment_status = self._get_param(request, 'status', 'Status')

        if not authority:
            return _cancel_redirect("InvalidRequest")

        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(authority=authority)
            except Payment.DoesNotExist:
                return _cancel_redirect("PaymentNotFound")

            if payment.status == PaymentStatus.SUCCESS:
                return _verify_redirect(payment.ref_id)

            if payment.status in [PaymentStatus.FAILED, PaymentStatus.CANCELED]:
                reason = getattr(payment, 'fail_reason', None) or (
                    "CanceledByUser" if payment.status == PaymentStatus.CANCELED else "GatewayRejected"
                )
                return _cancel_redirect(reason)

            # بررسی لغو توسط کاربر
            if payment_status is not None and str(payment_status).strip().lower() in ('0', 'nok', 'nack', 'cancel',
                                                                                      'canceled', 'cancelled', 'false'):
                payment.status = PaymentStatus.CANCELED
                if hasattr(payment, 'fail_reason'):
                    payment.fail_reason = "CanceledByUser"
                    payment.save(update_fields=['status', 'fail_reason'])
                else:
                    payment.save(update_fields=['status'])
                return _cancel_redirect("CanceledByUser")

            # درخواست وریفای به درگاه آقای پرداخت
            aqaye_service = AqayePardakhtService()
            verify_response = aqaye_service.verify_payment(
                amount_toman=int(payment.amount),
                transid=authority
            )

            payment.raw_verify = verify_response

            if verify_response.get("success"):
                payment.status = PaymentStatus.SUCCESS
                payment.ref_id = verify_response.get("ref_id", "")
                payment.card_pan = verify_response.get("card_pan", "")
                payment.verified_at = timezone.now()
                payment.save()

                from apps.profiles.models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=payment.user)
                profile.subscribe(payment.subscription)

                if payment.discount:
                    DiscountUsage.objects.create(discount=payment.discount, user=payment.user)
                    # استفاده از F برای جلوگیری از Race Condition
                    payment.discount.current_uses = F('current_uses') + 1
                    payment.discount.save(update_fields=['current_uses'])

                return _verify_redirect(payment.ref_id)

            else:
                payment.status = PaymentStatus.FAILED
                if hasattr(payment, 'fail_reason'):
                    payment.fail_reason = "GatewayRejected"
                    payment.save(update_fields=['status', 'fail_reason', 'raw_verify'])
                else:
                    payment.save(update_fields=['status', 'raw_verify'])
                return _cancel_redirect("GatewayRejected")

    def get(self, request, *args, **kwargs):
        return self._handle_callback(request)

    def post(self, request, *args, **kwargs):
        return self._handle_callback(request)