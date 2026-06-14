from django.utils import timezone
from django.db import models
from django.apps import apps
from jdatetime import datetime
from django_jalali.db import models as jmodels
from django.conf import settings
import jdatetime
from apps.music.models import *
from datetime import timedelta


class UserProfile(models.Model):
    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل کاربران'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile', verbose_name="کاربر")
    profile_image = models.ImageField(upload_to='profile_images/', default='https://dl.classicalmusicofficial.com/media/defualt/pro.png', verbose_name="تصویر پروفایل")
    joined_date = jmodels.jDateField(auto_now_add=True, verbose_name="تاریخ عضویت")


    def __str__(self):
        return str(self.user.phone_number)


class ArtistProfile(models.Model):
    artist = models.OneToOneField("music.Artist",on_delete=models.CASCADE,related_name="profile")

    def __str__(self):
        return self.artist.name
