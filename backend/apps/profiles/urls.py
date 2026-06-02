from django.urls import path
from .views import *


app_name = "profiles"

urlpatterns = [

    path("", ProfileView.as_view(), name="profiles"),

    path("update/", UpdateProfileView.as_view(), name="change_info"),

    path("change-password/", ChangePasswordView.as_view(), name="change_password"),

]
