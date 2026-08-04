from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlaylistViewSet, UserPlaylistViewSet

router = DefaultRouter()

router.register(r'public', PlaylistViewSet, basename='public-playlist')

router.register(r'me', UserPlaylistViewSet, basename='user-playlist')

app_name = 'playlists'

urlpatterns = [
    path('api/v1/', include(router.urls)),
]