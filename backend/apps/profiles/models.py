from django.utils import timezone
from django.db import models
from django.apps import apps
from jdatetime import datetime
from django_jalali.db import models as jmodels
from django.conf import settings
import jdatetime
from apps.music.models import *

class UserProfile(models.Model):
    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل کاربران'
        indexes = [models.Index(fields=["subscription_end_date"]),]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='profile',verbose_name="کاربر")

    profile_image = models.ImageField(upload_to='profile_images/',default='https://dl.classicalmusicofficial.com/media/defualt/pro.png',verbose_name="تصویر پروفایل")

    joined_date = jmodels.jDateField(auto_now_add=True,verbose_name="تاریخ عضویت")

    subscription = models.OneToOneField('subscriptions.Subscription',on_delete=models.CASCADE , null=True,blank=True,verbose_name="اشتراک")

    subscription_start_date = jmodels.jDateField(null=True,blank=True,verbose_name="تاریخ شروع اشتراک")

    subscription_end_date = jmodels.jDateField(null=True,blank=True,verbose_name="تاریخ پایان اشتراک")

    def __str__(self):
        return str({self.user.phone_number})

    @property
    def days_until_expiration(self):
        if not self.subscription_end_date:
            return 0

        now_jdate = jdatetime.date.today()

        end_date = self.subscription_end_date
        if isinstance(end_date, jdatetime.datetime):
            end_date = end_date.date()

        if end_date <= now_jdate:
            return 0

        diff = end_date - now_jdate
        return diff.days


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


    def extend_subscription(self, days):
        if not self.subscription:
            return False

        now_gregorian = timezone.now().date()
        now_jdate = datetime.date.fromgregorian(date=now_gregorian)

        SubscriptionHistory = apps.get_model("subscriptions", "SubscriptionHistory")

        # Update the end date
        if self.subscription_end_date:
            self.subscription_end_date = (self.subscription_end_date + datetime.timedelta(days=days))
        else:
            self.subscription_start_date = now_jdate
            self.subscription_end_date = (self.subscription_start_date + datetime.timedelta(days=days))

        self.save()
        return True


class ArtistProfile(models.Model):
    artist = models.OneToOneField("music.Artist", on_delete=models.CASCADE, related_name="profile")
    instagram_url = models.URLField(blank=True)
    spotify_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    long_bio = models.TextField(blank=True)
