from django.utils import timezone

from django.db import models
from django.apps import apps

from apps.accounts.models import CustomUser

from jdatetime import datetime, timedelta
from secrets import randbelow
from django_jalali.db import models as jmodels


class UserProfile(models.Model):
    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل کاربران'
        indexes = [
            models.Index(fields=["subscription_end_date"]),
        ]

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="کاربر"
    )
    profile_image = models.ImageField(
        upload_to='profile_images/',
        default='https://dl.classicalmusicofficial.com/media/defualt/pro.png',
        verbose_name="تصویر پروفایل"
    )
    joined_date = jmodels.jDateField(
        auto_now_add=True,
        verbose_name="تاریخ عضویت"
    )

    subscription = models.ForeignKey("subscriptions.Subscription",on_delete=models.CASCADE , null=True,blank=True,verbose_name="اشتراک")

    subscription_start_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name="تاریخ شروع اشتراک"
    )

    subscription_end_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name="تاریخ پایان اشتراک"
    )

    verification_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name="کد تایید"
    )
    is_phone_verified = models.BooleanField(
        default=False,
        verbose_name="تایید شماره تلفن"
    )
    verification_code_created_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان ایجاد کد تایید"
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def days_until_expiration(self):
        """Returns number of days until subscription expires, or None if no active subscription"""
        if self.subscription_start_date and self.subscription_end_date:
            # now_jdate = jdatetime.date.fromgregorian(date=timezone.now().date())
            now_jdate = datetime.fromgregorian(date=timezone.now().date())
            # Calculate difference in days
            days_diff = (self.subscription_end_date - now_jdate).days
            return days_diff if days_diff >= 0 else 0
        return None

    @property
    def is_subscription_active(self):
        if self.subscription and self.subscription_end_date:
            now_jdate = datetime.fromgregorian(
                date=timezone.now().date()
            )
            # Add a 1-day grace period (equivalent to 24 hours)
            return (self.subscription_end_date + timedelta(days=1)) > now_jdate
        return False

    def check_subscription_status(self):
        """Check subscription status and return appropriate message"""
        if not self.subscription:
            return "اشتراک فعالی ندارید"

        if not self.is_subscription_active:
            return "اشتراک منقضی شده است"

        days_left = self.days_until_expiration
        if days_left is not None:
            if days_left <= 7:
                return f"اشتراک شما در {days_left} روز منقضی میشود"
            return f"{days_left} روز باقی مانده تا منقضی شدن اشتراک شما"

        return "وضعیت اشتراک نامشخص است"

    def generate_verification_code(self):
        """Generate a 6-digit verification code"""
        code = ''.join([str(randbelow(10)) for _ in range(6)])
        self.verification_code = code
        self.verification_code_created_at = timezone.now()
        self.save()
        return code

    def verify_phone(self, code):
        """Verify phone number with the provided code"""
        if not code or not self.verification_code:
            return False

        # Check if code matches and is within 2-minute window
        if (
            self.verification_code == str(code).strip()
            and self.verification_code_created_at
            and (timezone.now() - self.verification_code_created_at)
            < timezone.timedelta(minutes=2)
        ):
            self.is_phone_verified = True
            self.verification_code = None
            self.verification_code_created_at = None
            self.save()
            return True
        return False

    def subscribe(self, subscription):
        """
        فعال کردن/تمدید اشتراک.
        توجه: تاریخ شروع/پایان به صورت جلالی ذخیره می‌شود.
        """
        # زمان فعلی میلادی و تبدیل به جلالی
        now_gregorian = timezone.now().date()
        now_jdate = datetime.fromgregorian(date=now_gregorian)

        # ثبت در تاریخچه (start_date جلالی)
        SubscriptionHistory = apps.get_model("subscriptions", "SubscriptionHistory")

        self.subscription = subscription

        if self.is_subscription_active:
            # اگر اشتراک فعال است، تاریخ پایان را به روز کن
            self.subscription_end_date = (
                self.subscription_end_date
                + datetime.timedelta(days=subscription.duration_days)
            )
        else:
            # اگر اشتراک فعال نداریم، از امروز شروع می‌کنیم
            self.subscription_start_date = now_jdate
            self.subscription_end_date = now_jdate + datetime.timedelta(
                days=subscription.duration_days
            )

        self.save()
        return True

    def extend_subscription(self, days):
        if not self.subscription:
            return False

        now_gregorian = timezone.now().date()
        now_jdate = datetime.date.fromgregorian(date=now_gregorian)

        SubscriptionHistory = apps.get_model("subscriptions", "SubscriptionHistory")

        # Update the end date
        if self.subscription_end_date:
            self.subscription_end_date = (
                self.subscription_end_date + datetime.timedelta(days=days)
            )
        else:
            self.subscription_start_date = now_jdate
            self.subscription_end_date = (
                self.subscription_start_date
                + datetime.timedelta(days=days)
            )

        self.save()
        return True
