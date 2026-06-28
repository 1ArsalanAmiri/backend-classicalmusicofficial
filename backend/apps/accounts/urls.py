from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *
from ..common.views import *


app_name = "accounts"


urlpatterns = [

    path("send-otp/", SendOTPView.as_view(), name="send_otp"),

    path("verify-otp/", VerifyOTPView.as_view(), name="verify_otp"),

    path('change-phone/request/', RequestChangePhoneNumberView.as_view(), name='request_change_phone'),

    path('change-phone/verify/', VerifyChangePhoneNumberView.as_view(), name='verify_change_phone'),

    path("reset-password/", ResetPasswordView.as_view(), name="change_password"),

    path("logout/", LogoutView.as_view() , name = "logout"),

    path('delete-account/verify/', VerifyDeleteAccountView.as_view(), name='verify_delete_account'),

    path("delete-account/", DeleteAccountView.as_view(), name = "delete_account"),

    path("login-password/", LoginView.as_view(), name = "login"),

    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

]
