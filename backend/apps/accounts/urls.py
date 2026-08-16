from django.urls import path
from .views import (
    LoginView, LogoutView, ResetPasswordView,
    RequestDeleteAccountOTPView, VerifyDeleteAccountView,
    CustomTokenObtainPairView, CustomTokenRefreshView
)

app_name = "accounts"

urlpatterns = [
    path("reset-password/", ResetPasswordView.as_view(), name="change_password"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("delete-account/request/", RequestDeleteAccountOTPView.as_view(), name="request_delete_account"),
    path("delete-account/verify/", VerifyDeleteAccountView.as_view(), name="verify_delete_account"),
    path("login-password/", LoginView.as_view(), name="login"),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
]