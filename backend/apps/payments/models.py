from datetime import timezone
from django.db import models
from jdatetime import datetime
from apps.accounts.models import CustomUser
from apps.subscriptions.models import Subscription
from django_jalali.db import models as jmodels




class Discount(models.Model):
    class Meta:
        verbose_name = 'تخفیف'
        verbose_name_plural = 'تخفیف‌ها'
        ordering = ['-created_at']

    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'درصدی'),
        ('fixed', 'مبلغ ثابت'),
    ]

    DISCOUNT_SCOPE_CHOICES = [
        ('all', 'همه اشتراک‌ها'),
        ('specific', 'اشتراک خاص'),
        ('category', 'دسته‌بندی خاص'),
    ]

    name = models.CharField(max_length=100, verbose_name="نام تخفیف")
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="کد تخفیف",
        help_text="کد منحصر به فرد تخفیف"
    )
    description = models.TextField(
        verbose_name="توضیحات",
        help_text="توضیحات تخفیف"
    )

    # Discount details
    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,
        default='percentage',
        verbose_name="نوع تخفیف"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="مقدار تخفیف",
        help_text="در صورت درصدی: عدد بین 0 تا 100، در صورت مبلغ ثابت: مبلغ به تومان"
    )

    # Scope and applicability
    discount_scope = models.CharField(
        max_length=10,
        choices=DISCOUNT_SCOPE_CHOICES,
        default='all',
        verbose_name="محدوده تخفیف"
    )
    applicable_subscriptions = models.ManyToManyField(
        Subscription,
        blank=True,
        verbose_name="اشتراک‌های قابل اعمال",
        help_text="در صورت انتخاب 'اشتراک خاص' این فیلد الزامی است"
    )

    # Usage limits
    max_uses = models.PositiveIntegerField(
        default=1,
        verbose_name="حداکثر تعداد استفاده",
        help_text="0 برای نامحدود"
    )
    current_uses = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد استفاده شده"
    )
    max_uses_per_user = models.PositiveIntegerField(
        default=1,
        verbose_name="حداکثر استفاده هر کاربر",
        help_text="هر کاربر چند بار می‌تواند از این تخفیف استفاده کند"
    )

    # Time constraints (تاریخ جلالی)
    start_date = jmodels.jDateField(
        verbose_name="تاریخ شروع تخفیف"
    )
    end_date = jmodels.jDateField(
        verbose_name="تاریخ پایان تخفیف"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال"
    )

    # Tracking
    created_at = jmodels.jDateField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )
    updated_at = jmodels.jDateField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی"
    )

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validate discount value based on type
        if self.discount_type == 'percentage':
            if self.discount_value < 0 or self.discount_value > 100:
                raise ValidationError('درصد تخفیف باید بین 0 تا 100 باشد')
        else:  # fixed amount
            if self.discount_value <= 0:
                raise ValidationError('مبلغ تخفیف باید بزرگتر از صفر باشد')

        # Validate dates
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError('تاریخ شروع باید قبل از تاریخ پایان باشد')

        # Validate scope and applicable subscriptions
        # فقط وقتی pk دارد (یعنی ذخیره شده) سراغ ManyToMany می‌رویم
        if (
            self.discount_scope == 'specific'
            and self.pk
            and not self.applicable_subscriptions.exists()
        ):
            raise ValidationError(
                'در صورت انتخاب اشتراک خاص، حداقل یک اشتراک باید انتخاب شود'
            )

    def is_valid(self):
        """Check if discount is valid for use"""
        # تبدیل زمان فعلی میلادی به جلالی برای مقایسه با jDateField
        now_gregorian = timezone.now().date()
        now_jdate = datetime.fromgregorian(date=now_gregorian)

        # Check if discount is active
        if not self.is_active:
            return False, "تخفیف غیرفعال است"

        # Check date validity
        if now_jdate < self.start_date:
            return False, "تخفیف هنوز شروع نشده است"

        if now_jdate > self.end_date:
            return False, "تخفیف منقضی شده است"

        # Check usage limits
        if 0 < self.max_uses <= self.current_uses:
            return False, "حداکثر تعداد استفاده از تخفیف رسیده است"

        return True, "تخفیف معتبر است"

    def can_be_used_by_user(self, user):
        """Check if user can use this discount"""
        from apps.payments.models import DiscountUsage

        # Check if user has already used this discount maximum times
        usage_count = DiscountUsage.objects.filter(
            discount=self,
            user=user
        ).count()

        if usage_count >= self.max_uses_per_user:
            return False, f"شما قبلاً {self.max_uses_per_user} بار از این تخفیف استفاده کرده‌اید"

        return True, "کاربر می‌تواند از این تخفیف استفاده کند"

    def apply_to_subscription(self, subscription):
        """Apply discount to a subscription and return discounted price"""
        # Check if subscription is applicable
        if self.discount_scope == 'specific' and subscription not in self.applicable_subscriptions.all():
            return None, "این تخفیف برای این اشتراک قابل اعمال نیست"

        original_price = subscription.price

        if self.discount_type == 'percentage':
            discount_amount = int((original_price * self.discount_value) / 100)
            discounted_price = original_price - discount_amount
        else:  # fixed amount
            discount_amount = self.discount_value
            discounted_price = original_price - discount_amount
            if discounted_price < 0:
                discounted_price = 0

        return discounted_price, discount_amount

    def use_discount(self, user, subscription):
        """Use the discount for a user and subscription"""
        # Validate discount
        is_valid, message = self.is_valid()
        if not is_valid:
            return False, message

        # Check user eligibility
        can_use, message = self.can_be_used_by_user(user)
        if not can_use:
            return False, message

        # Check subscription applicability
        discounted_price, discount_amount = self.apply_to_subscription(
            subscription
        )
        if discounted_price is None:
            return False, discount_amount  # discount_amount contains error message

        # Create usage record
        DiscountUsage.objects.create(
            discount=self,
            user=user,
            subscription=subscription,
            original_price=subscription.price,
            discounted_price=discounted_price,
            discount_amount=discount_amount
        )

        # Update usage count
        self.current_uses += 1
        self.save()

        return True, {
            'discounted_price': discounted_price,
            'discount_amount': discount_amount,
            'original_price': subscription.price
        }


class DiscountUsage(models.Model):
    class Meta:
        verbose_name = 'استفاده از تخفیف'
        verbose_name_plural = 'استفاده‌های تخفیف'
        ordering = ['-used_at']

    discount = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        verbose_name="تخفیف"
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="کاربر"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        verbose_name="اشتراک"
    )
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="قیمت اصلی"
    )
    discounted_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="قیمت با تخفیف"
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="مقدار تخفیف اعمال شده"
    )
    # جلالی به صورت date؛ نیازی به strftime نیست
    used_at = jmodels.jDateField(
        auto_now_add=True,
        verbose_name="تاریخ استفاده"
    )

    def __str__(self):
        return f"{self.user.username} - {self.discount.code} - {self.used_at}"