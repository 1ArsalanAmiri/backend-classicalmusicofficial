from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

User = get_user_model()


class AuthenticationAPITests(APITestCase):

    def setUp(self):
        """
        این متد قبل از هر تست اجرا می‌شود و داده‌های اولیه (کاربر و رمز عبور) را ایجاد می‌کند.
        """
        self.phone_number = "+989123456789"
        self.password = "StrongPassword123!"
        self.user = User.objects.create_user(
            phone_number=self.phone_number,
            password=self.password,
            first_name="تست",
            last_name="کاربر"
        )

        # تولید توکن برای تست‌هایی که نیاز به احراز هویت دارند
        self.refresh = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh.access_token)

        # آدرس‌های URL (بر اساس نام‌گذاری شما در فایل urls.py)
        self.login_url = reverse("accounts:login")
        self.logout_url = reverse("accounts:logout")
        self.change_phone_url = reverse("accounts:change_phone_number")
        self.reset_password_url = reverse("accounts:change_password")

    # ==========================================
    # تست‌های مربوط به ورود (LoginView)
    # ==========================================
    def test_login_success(self):
        """بررسی ورود موفقیت‌آمیز با اطلاعات صحیح"""
        data = {
            "phone_number": self.phone_number,
            "password": self.password
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["message"], "Authenticated successfully")

    def test_login_invalid_credentials(self):
        """بررسی خطای ورود با رمز عبور اشتباه"""
        data = {
            "phone_number": self.phone_number,
            "password": "WrongPassword!"
        }
        response = self.client.post(self.login_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # تست‌های مربوط به خروج (LogoutView)
    # ==========================================
    def test_logout_success(self):
        """بررسی خروج موفق و بلک‌لیست شدن توکن"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        data = {
            "phone_number": self.phone_number,
            "refresh": str(self.refresh)
        }
        response = self.client.post(self.logout_url, data)

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(response.data["message"], "Logout Success, Blacklisted Token. ")

    def test_logout_without_auth(self):
        """بررسی جلوگیری از خروج کاربری که احراز هویت نشده است"""
        data = {
            "phone_number": self.phone_number,
            "refresh": str(self.refresh)
        }
        response = self.client.post(self.logout_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_wrong_user_token(self):
        """بررسی جلوگیری از خروج با توکن یک کاربر دیگر"""
        # ایجاد کاربر دوم
        other_user = User.objects.create_user(phone_number="+989999999999", password="TestPassword1!")
        other_refresh = RefreshToken.for_user(other_user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        data = {
            "phone_number": self.phone_number,
            "refresh": str(other_refresh)  # ارسال ریفرش توکن کاربر دیگر
        }
        response = self.client.post(self.logout_url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "You Dont Have Permission For This Operation.")

    # ==========================================
    # تست‌های تغییر شماره (ChangePhoneNumberView)
    # ==========================================
    def test_change_phone_number_success(self):
        """بررسی تغییر موفقیت‌آمیز شماره موبایل"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        new_phone = "+989111111111"
        data = {
            "new_phone_number": new_phone
        }
        response = self.client.post(self.change_phone_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()  # بروزرسانی آبجکت کاربر از دیتابیس
        self.assertEqual(str(self.user.phone_number), new_phone)

    def test_change_phone_number_already_exists(self):
        """بررسی خطای تکراری بودن شماره موبایل جدید"""
        # ایجاد کاربر دوم با شماره‌ای که قصد داریم به آن تغییر دهیم
        existing_phone = "+989222222222"
        User.objects.create_user(phone_number=existing_phone, password="Password123!")

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        data = {
            "new_phone_number": existing_phone
        }
        response = self.client.post(self.change_phone_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Phone number already used")

    # ==========================================
    # تست‌های بازیابی رمز عبور (ResetPasswordView)
    # ==========================================
    def test_reset_password_success(self):
        """بررسی تغییر موفقیت‌آمیز رمز عبور با OTP صحیح"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        cache.set(f"otp:{self.phone_number}", "123456", timeout=300)

        data = {
            "phone_number": self.phone_number,
            "otp": "123456",
            "new_password": "NewStrongPassword123!",
            "new_password_confirm": "NewStrongPassword123!",
        }
        response = self.client.post(self.reset_password_url, data)

        # فرض بر این است که ویو شما در صورت موفقیت کد 200 برمی‌گرداند
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # بررسی اینکه آیا با رمز جدید می‌توان لاگین کرد
        login_response = self.client.post(self.login_url, {
            "phone_number": self.phone_number,
            "password": "NewStrongPassword123!"
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_reset_password_mismatch(self):
        """بررسی خطای عدم تطابق رمزهای عبور جدید"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        data = {
            "phone_number": self.phone_number,
            "otp": "123456",
            "new_password": "NewStrongPassword123!",
            "new_password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(self.reset_password_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Passwords do not match", str(response.data))
