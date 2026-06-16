from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProfileView,
    UpdateProfileView,
    ChangePasswordView,
    ArtistProfileViewSet,
    UserDashboardViewSet
)

router = DefaultRouter()
router.register(r'dashboard', UserDashboardViewSet, basename='user-dashboard')
router.register(r'artists', ArtistProfileViewSet, basename='artist-profile')

urlpatterns = [
    path('me/', ProfileView.as_view(), name='my-profile'),
    path('me/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change-password'),

    path('', include(router.urls)),
]
