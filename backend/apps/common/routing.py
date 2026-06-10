from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/album-zip/(?P<album_slug>[\w-]+)/$', consumers.AlbumZipConsumer.as_asgi()),
]
