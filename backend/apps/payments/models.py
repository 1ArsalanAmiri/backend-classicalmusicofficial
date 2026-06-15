from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.subscriptions.models import Subscription


class DiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', 'درصدی'
    FIXED = 'fixed', 'مبلغ ثابت'


class DiscountScope(models.TextChoices):
    ALL = 'all', 'همه اشتراک‌ها'
    SPECIFIC = 'specific', 'اشتراک خاص'
    CATEGORY = 'category', 'دسته‌بندی خاص'


class Discount(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام تخفیف")
    code = models.CharField(max_length=50, unique=True, verbose_name="کد تخفیف")
    description = models.TextField(blank=True, verbose_name="توضیحات")

    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE,
                                     verbose_name="نوع تخفیف")
    discount_value = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="مقدار تخفیف")

    discount_scope = models.CharField(max_length=20, choices=DiscountScope.choices, default=DiscountScope.ALL,
                                      verbose_name="محدوده تخفیف")
    applicable_subscriptions = models.ManyToManyField(Subscription, blank=True, verbose_name="اشتراک‌های قابل اعمال")

    max_uses = models.PositiveIntegerField(default=1, verbose_name="حداکثر استفاده کل", help_text="0 برای نامحدود")
    current_uses = models.PositiveIntegerField(default=0, verbose_name="تعداد استفاده شده")
    max_uses_per_user = models.PositiveIntegerField(default=1, verbose_name="حداکثر استفاده هر کاربر")

    start_date = models.DateTimeField(verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(verbose_name="تاریخ پایان")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تخفیف'
        verbose_name_plural = 'تخفیف‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.code}"

    def clean(self):
        if self.discount_type == DiscountType.PERCENTAGE and not (0 < self.discount_value <= 100):
            raise ValidationError("درصد تخفیف باید بین 1 تا 100 باشد.")
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("تاریخ شروع باید قبل از تاریخ پایان باشد.")

    def is_valid_for_use(self, user, subscription=None):
        now = timezone.now()

        if not self.is_active:
            return False, "این کد تخفیف غیرفعال است."
        if now < self.start_date or now > self.end_date:
            return False, "این کد تخفیف منقضی شده یا هنوز شروع نشده است."
        if 0 < self.max_uses <= self.current_uses:
            return False, "ظرفیت استفاده از این کد تخفیف تکمیل شده است."

        user_uses = DiscountUsage.objects.filter(discount=self, user=user).count()
        if user_uses >= self.max_uses_per_user:
            return False, "شما به حداکثر دفعات مجاز استفاده از این کد رسیده‌اید."

        if subscription and self.discount_scope == DiscountScope.SPECIFIC:
            if not self.applicable_subscriptions.filter(id=subscription.id).exists():
                return False, "این کد تخفیف برای این اشتراک معتبر نیست."

        return True, "معتبر"

    def calculate_discount_amount(self, original_price):
        if self.discount_type == DiscountType.PERCENTAGE:
            return (original_price * self.discount_value) / 100
        return min(self.discount_value, original_price)


class DiscountUsage(models.Model):
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, related_name='usages', verbose_name="تخفیف")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='discount_usages',
                             verbose_name="کاربر")
    used_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ استفاده")

    class Meta:
        verbose_name = 'استفاده از تخفیف'
        verbose_name_plural = 'استفاده‌های تخفیف'


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    CANCELED = "canceled", "Canceled"


class Payment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="اشتراک خریداری شده",
        null=True,
        blank=True,
    )

    discount = models.ForeignKey(
        Discount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="کد تخفیف استفاده شده"
    )
    amount = models.PositiveBigIntegerField(verbose_name="مبلغ نهایی (تومان)")
    description = models.CharField(max_length=255, null=True, blank=True)

    authority = models.CharField(max_length=255, unique=True, null=True, blank=True)
    ref_id = models.CharField(max_length=255, null=True, blank=True, verbose_name="کد پیگیری درگاه")
    card_pan = models.CharField(max_length=20, null=True, blank=True,
                                verbose_name="شماره کارت ماسک شده")

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    mobile = models.CharField(max_length=20, blank=True)

    raw_request = models.JSONField(null=True, blank=True)
    raw_verify = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"

    def __str__(self):
        return f"Payment {self.id} - {self.user} - {self.status}"


