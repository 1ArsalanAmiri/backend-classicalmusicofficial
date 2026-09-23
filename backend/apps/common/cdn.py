from rest_framework import serializers


def build_cdn_url(request, relative_path):
    if not relative_path:
        return None
    relative_path = str(relative_path).lstrip('/')
    path = f"/video-cdn/{relative_path}"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


class CDNImageField(serializers.ImageField):
    def to_representation(self, value):
        if not value:
            return None
        request = self.context.get('request')
        return build_cdn_url(request, value.name)