from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProfileView,
    ArtistProfileViewSet,
    UpdateProfileView,
    ChangePasswordView,
)

app_name = "profiles"

router = DefaultRouter()
router.register(r"artists", ArtistProfileViewSet, basename="artist-profile")

urlpatterns = [
    path("", include(router.urls)),

    path("me/", ProfileView.as_view(), name="profile"),
    path("me/update/", UpdateProfileView.as_view(), name="change_info"),
    path("me/change-password/", ChangePasswordView.as_view(), name="change_password"),
]
