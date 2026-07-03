from django.db import models
from django_jalali.db import models as jmodels



class Subscription(models.Model):

    SUBSCRIPTION_CHOICES = [
        ('online', 'فقط پخش آنلاین'),
        ('download', 'فقط دانلود'),
        ('videos' , 'دانلود ویدیو ها'),
        ('both', 'دانلود و پخش'),
        ('all' , 'همه قابلیت ها')
    ]

    class Meta:
        verbose_name = 'اشتراک'
        verbose_name_plural = 'اشتراک‌ها'

        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='subscription_price_gte_0'
            ),
            models.CheckConstraint(
                condition=models.Q(duration_days__gt=0),
                name='subscription_duration_gt_0'
            ),
        ]

    name = models.CharField(max_length=100,verbose_name="نام اشتراک",unique=True)

    price = models.DecimalField(max_digits=20,decimal_places=0,verbose_name="قیمت (تومان)")

    duration_days = models.IntegerField(verbose_name="مدت زمان (روز)")

    subscription_type = models.CharField(max_length=20,choices=SUBSCRIPTION_CHOICES,default='both',verbose_name="نوع اشتراک")

    has_permanent_discount = models.BooleanField(default=False,verbose_name="تخفیف دائمی دارد")

    discounted_price = models.DecimalField(max_digits=20,decimal_places=0,null=True,blank=True,verbose_name="قیمت با تخفیف")

    discount_percentage = models.PositiveIntegerField(null=True,blank=True,verbose_name="درصد تخفیف",help_text="به صورت خودکار محاسبه می‌شود")

    discount_label = models.CharField(max_length=50,null=True,blank=True,verbose_name="برچسب تخفیف",help_text="مثلاً: تخفیف ویژه، حراج نوروزی، ...")

    def save(self, *args, **kwargs):
        if self.has_permanent_discount and self.discounted_price is not None and self.price > 0:
            if self.discounted_price < self.price:
                discount_amount = self.price - self.discounted_price
                self.discount_percentage = int((discount_amount / self.price) * 100)
            else:
                self.has_permanent_discount = False
                self.discounted_price = None
                self.discount_percentage = None
        elif not self.has_permanent_discount:
            self.discounted_price = None
            self.discount_percentage = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.duration_days} days"



class SubscriptionHistory(models.Model):
    class Meta:
        verbose_name = 'تاریخچه اشتراک'
        verbose_name_plural = 'تاریخچه اشتراک‌ها'
        ordering = ['-start_date']

    user_profile = models.ForeignKey(
        "profiles.UserProfile",
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

