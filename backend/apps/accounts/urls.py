from django.urls import path
from .views import *



app_name = "accounts"

urlpatterns = [

    path("register/", RegisterView.as_view() , name = "register"),

    path("login/", LoginView.as_view() , name = "login"),

    path("logout/", LogoutView.as_view() , name = "logout"),

    path("change_password/", ChangePasswordView.as_view(), name="change_password"),

    path("profile/", ProfileView.as_view() , name = "profiles"),

    path("profile/update/" , UpdateProfileView.as_view() , name = "change_info"),




]
