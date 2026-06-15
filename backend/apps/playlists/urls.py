from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlaylistViewSet

router = DefaultRouter()

router.register(r'', PlaylistViewSet, basename='playlist')

app_name = 'playlists'

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
