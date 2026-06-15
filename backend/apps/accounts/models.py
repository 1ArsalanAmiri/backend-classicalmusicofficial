from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django_jalali.db import models as jmodels
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone



class CustomUserManager(BaseUserManager):

    def create_user(self, phone_number, password=None, **extra_fields):

        if not phone_number:
            raise ValueError('شماره تلفن الزامی است')

        user = self.model(phone_number=phone_number,**extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(phone_number, password, **extra_fields)



class CustomUser(AbstractUser):
    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'


    phone_number = PhoneNumberField(unique=True,region="IR",verbose_name="شماره موبایل")

    email = models.EmailField(blank=True, null=True, verbose_name="ایمیل")

    username = models.CharField(max_length=20, unique=True, verbose_name="نام کاربری" , blank=True, null=True)

    first_name = models.CharField(max_length=20, blank=True, verbose_name="نام")

    last_name = models.CharField(max_length=20, blank=True, verbose_name="نام خانوادگی")

    is_active = models.BooleanField(default=True, verbose_name="فعال")

    is_staff = models.BooleanField(default=False, verbose_name="کارمند")

    is_superuser = models.BooleanField(default=False, verbose_name="مدیر کل")

    date_joined = jmodels.jDateField(auto_now_add=True, verbose_name="تاریخ عضویت")

    last_login = models.DateTimeField(null=True, blank=True, verbose_name="آخرین ورود")

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []


    def __str__(self):
        return str(self.phone_number)


    def PhoneNumber(self):
        return self.phone_number
