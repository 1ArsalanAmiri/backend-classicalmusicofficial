from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator
from django_jalali.db import models as jmodels
import secrets
import jdatetime


class CustomUserManager(BaseUserManager):
    def create_user(self, username, phone_number, password=None, **extra_fields):
        if not username:
            raise ValueError('نام کاربری الزامی است')
        if not phone_number:
            raise ValueError('شماره تلفن الزامی است')

        user = self.model(
            username=username,
            phone_number=phone_number,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, phone_number, password, **extra_fields)


class CustomUser(AbstractUser):
    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    phone_regex = RegexValidator(
        regex=r'^09[0-9]{9}$',
        message="شماره تلفن باید با 09 شروع شود و 11 رقم باشد"
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=11,
        unique=True,
        verbose_name="شماره تلفن"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="ایمیل")
    username = models.CharField(
        max_length=150, unique=True, verbose_name="نام کاربری"
    )
    first_name = models.CharField(
        max_length=150, blank=True, verbose_name="نام"
    )
    last_name = models.CharField(
        max_length=150, blank=True, verbose_name="نام خانوادگی"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_staff = models.BooleanField(default=False, verbose_name="کارمند")
    is_superuser = models.BooleanField(default=False, verbose_name="مدیر کل")
    # تاریخ عضویت به صورت جلالی (فقط تاریخ، بدون زمان)
    date_joined = jmodels.jDateField(
        auto_now_add=True, verbose_name="تاریخ عضویت"
    )
    # آخرین ورود میلادی، برای سازگاری با auth و DRF
    last_login = models.DateTimeField(
        null=True, blank=True, verbose_name="آخرین ورود"
    )

    # رفع مشکل reverse accessor با تعریف related_name
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone_number']

    def __str__(self):
        return self.username

    # این متد عملاً اضافی بود، اگر جایی در کد فرانت یا بک‌اند از آن استفاده می‌کنی، نگهش داریم
    def phoneNumber(self):
        return self.phone_number


class Subscription(models.Model):
    class Meta:
        verbose_name = 'اشتراک'
        verbose_name_plural = 'اشتراک‌ها'

    name = models.CharField(
        max_length=100,
        verbose_name="نام اشتراک",
        unique=True
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        verbose_name="قیمت"
    )
    duration_days = models.IntegerField(verbose_name="مدت زمان (روز)")

    SUBSCRIPTION_CHOICES = [
        ('online', 'فقط پخش آنلاین'),
        ('download', 'فقط دانلود'),
        ('both', 'دانلود و پخش'),
    ]
    subscription_type = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default='both',
        verbose_name="نوع اشتراک"
    )

    # فیلدهای تخفیف دائمی
    has_permanent_discount = models.BooleanField(
        default=False,
        verbose_name="تخفیف دائمی دارد"
    )
    discounted_price = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="قیمت با تخفیف"
    )
    discount_percentage = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="درصد تخفیف",
        help_text="به صورت خودکار محاسبه می‌شود"
    )
    discount_label = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="برچسب تخفیف",
        help_text="مثلاً: تخفیف ویژه، حراج نوروزی، ..."
    )

    def save(self, *args, **kwargs):
        # محاسبه خودکار درصد تخفیف اگر قیمت تخفیف خورده وارد شده
        if self.has_permanent_discount and self.discounted_price and self.price > 0:
            if self.discounted_price < self.price:
                discount_amount = self.price - self.discounted_price
                self.discount_percentage = int(
                    (discount_amount / self.price) * 100
                )
            else:
                # اگر قیمت تخفیف از قیمت اصلی بیشتر بود، تخفیف رو غیرفعال کن
                self.has_permanent_discount = False
                self.discounted_price = None
                self.discount_percentage = None
        elif not self.has_permanent_discount:
            self.discounted_price = None
            self.discount_percentage = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.duration_days} days"


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
        now_jdate = jdatetime.date.fromgregorian(date=now_gregorian)

        # Check if discount is active
        if not self.is_active:
            return False, "تخفیف غیرفعال است"

        # Check date validity
        if now_jdate < self.start_date:
            return False, "تخفیف هنوز شروع نشده است"

        if now_jdate > self.end_date:
            return False, "تخفیف منقضی شده است"

        # Check usage limits
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False, "حداکثر تعداد استفاده از تخفیف رسیده است"

        return True, "تخفیف معتبر است"

    def can_be_used_by_user(self, user):
        """Check if user can use this discount"""
        from .models import DiscountUsage

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
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="اشتراک"
    )
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
    subscription_history = models.ManyToManyField(
        Subscription,
        through='SubscriptionHistory',
        related_name='subscribers_history',
        verbose_name="تاریخچه اشتراک‌ها"
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
    # اینجا به DateTimeField تغییر داده شد تا با timezone.now سازگار باشد
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
            now_jdate = jdatetime.date.fromgregorian(date=timezone.now().date())
            # Calculate difference in days
            days_diff = (self.subscription_end_date - now_jdate).days
            return days_diff if days_diff >= 0 else 0
        return None

    @property
    def is_subscription_active(self):
        if self.subscription and self.subscription_end_date:
            now_jdate = jdatetime.date.fromgregorian(
                date=timezone.now().date()
            )
            # Add a 1-day grace period (equivalent to 24 hours)
            return (self.subscription_end_date + jdatetime.timedelta(days=1)) > now_jdate
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
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        self.verification_code = code
        self.verification_code_created_at = timezone.now()
        self.save()
        return code

    def verify_phone(self, code):
        """Verify phone number with the provided code"""
        if not code or not self.verification_code:
            return False

        # Check if code matches and is within 2 minute window
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
        now_jdate = jdatetime.date.fromgregorian(date=now_gregorian)

        # ثبت در تاریخچه (start_date جلالی)
        SubscriptionHistory.objects.create(
            user_profile=self,
            subscription=subscription,
            start_date=now_jdate
        )

        self.subscription = subscription

        if self.is_subscription_active:
            # اگر اشتراک فعال است، تاریخ پایان را به روز کن
            self.subscription_end_date = (
                self.subscription_end_date
                + jdatetime.timedelta(days=subscription.duration_days)
            )
        else:
            # اگر اشتراک فعال نداریم، از امروز شروع می‌کنیم
            self.subscription_start_date = now_jdate
            self.subscription_end_date = now_jdate + jdatetime.timedelta(
                days=subscription.duration_days
            )

        self.save()
        return True

    def extend_subscription(self, days):
        if not self.subscription:
            return False

        now_gregorian = timezone.now().date()
        now_jdate = jdatetime.date.fromgregorian(date=now_gregorian)

        SubscriptionHistory.objects.create(
            user_profile=self,
            subscription=self.subscription,
            start_date=now_jdate,
            end_date=(
                self.subscription_end_date + jdatetime.timedelta(days=days)
                if self.subscription_end_date
                else None
            )
        )

        # Update the end date
        if self.subscription_end_date:
            self.subscription_end_date = (
                self.subscription_end_date + jdatetime.timedelta(days=days)
            )
        else:
            self.subscription_start_date = now_jdate
            self.subscription_end_date = (
                self.subscription_start_date
                + jdatetime.timedelta(days=days)
            )

        self.save()
        return True


class SubscriptionHistory(models.Model):
    class Meta:
        verbose_name = 'تاریخچه اشتراک'
        verbose_name_plural = 'تاریخچه اشتراک‌ها'
        ordering = ['-start_date']

    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        verbose_name="پروفایل کاربر"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        verbose_name="اشتراک"
    )
    start_date = jmodels.jDateField(verbose_name="تاریخ شروع")
    end_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name="تاریخ پایان"
    )

    def __str__(self):
        return f"{self.user_profile.user.username} - {self.subscription.name}"
