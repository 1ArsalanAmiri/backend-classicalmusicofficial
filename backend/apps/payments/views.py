from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Payment, PaymentStatus, Discount, DiscountUsage
from .services import AqayePardakhtService  # تغییر ایمپورت به سرویس جدید
from apps.subscriptions.models import Subscription


class PaymentRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        subscription_id = request.data.get('subscription_id')
        discount_code = request.data.get('discount_code')
        user = request.user

        if not subscription_id:
            return Response({"error": "ارسال شناسه اشتراک الزامی است."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return Response({"error": "اشتراک یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        base_price = subscription.discounted_price if subscription.has_permanent_discount else subscription.price
        final_amount = base_price
        discount_obj = None

        if discount_code:
            try:
                discount_obj = Discount.objects.get(code=discount_code, is_active=True)
                is_valid, msg = discount_obj.is_valid_for_use(user, subscription)
                if not is_valid:
                    return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

                discount_amount = discount_obj.calculate_discount_amount(base_price)
                final_amount = base_price - discount_amount

            except Discount.DoesNotExist:
                return Response({"error": "کد تخفیف نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        mobile = getattr(user, 'phone_number', '') or ''

        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            discount=discount_obj,
            amount=final_amount,
            status=PaymentStatus.PENDING,
            mobile=str(mobile),
            description=f"خرید اشتراک {subscription.name} برای {user.username}"
        )

        if final_amount <= 0:
            payment.status = PaymentStatus.SUCCESS
            payment.verified_at = timezone.now()
            payment.save()

            from apps.profiles.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=payment.user)
            profile.subscribe(subscription)

            if discount_obj:
                DiscountUsage.objects.create(discount=discount_obj, user=user)
                discount_obj.current_uses += 1
                discount_obj.save(update_fields=['current_uses'])

            return Response({"message": "اشتراک شما به صورت رایگان فعال شد.", "is_free": True},
                            status=status.HTTP_200_OK)

        callback_url = request.build_absolute_uri(reverse('payments:verify'))

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
            return Response({"error": api_response.get("error_message", "خطا در اتصال به درگاه")},
                            status=status.HTTP_502_BAD_GATEWAY)


class PaymentVerifyAPIView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        authority = request.query_params.get('transid')
        payment_status = request.query_params.get('status')

        frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')

        if not authority or not payment_status:
            return redirect(f"{frontend_base_url}/payment/result?status=failed&message=InvalidRequest")

        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(authority=authority)
            except Payment.DoesNotExist:
                return redirect(f"{frontend_base_url}/payment/result?status=failed&message=PaymentNotFound")

            if payment.status in [PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.CANCELED]:
                return redirect(f"{frontend_base_url}/payment/result?status={payment.status.lower()}")

            if payment_status == '0':
                payment.status = PaymentStatus.CANCELED
                payment.save(update_fields=['status'])
                return redirect(f"{frontend_base_url}/payment/result?status=canceled")

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
                    payment.discount.current_uses += 1
                    payment.discount.save(update_fields=['current_uses'])

                return redirect(f"{frontend_base_url}/payment/result?status=success&ref_id={payment.ref_id}")

            else:
                payment.status = PaymentStatus.FAILED
                payment.save()
                return redirect(f"{frontend_base_url}/payment/result?status=failed&message=GatewayRejected")