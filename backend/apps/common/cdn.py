from django.conf import settings
from rest_framework import serializers
from urllib.parse import urljoin


def build_cdn_url(request, relative_path):
    if not relative_path:
        return None

    relative_path = str(relative_path).lstrip('/')
    base_url = settings.MEDIA_URL

    if base_url.startswith('http://') or base_url.startswith('https://'):
        return urljoin(base_url, relative_path)

    path = urljoin(base_url, relative_path)
    if request is not None:
        return request.build_absolute_uri(path)
    return path


class CDNImageField(serializers.ImageField):
    def to_representation(self, value):
        if not value:
            return None
        request = self.context.get('request')
        return build_cdn_url(request, value.name)