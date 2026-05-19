from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *
from ..common.views import *


app_name = "accounts"


urlpatterns = [

    path("send-otp/", SendOTPView.as_view(), name="send_otp"),

    path("verify-otp/", VerifyOTPView.as_view(), name="verify_otp"),

    path("change-password/", ChangePasswordView.as_view(), name="change_password"),

    path("logout/", LogoutView.as_view() , name = "logout"),

    path("login-password/", LoginView.as_view(), name = "login"),

    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path("profile/", ProfileView.as_view() , name = "profiles"),

    path("profile/update/" , UpdateProfileView.as_view() , name = "change_info"),

]
