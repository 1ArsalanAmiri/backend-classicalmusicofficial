from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from .models import Video, PublishStatus
from ..subscriptions.services import user_has_all_access
from ..music.serializers import ArtistBasicSerializer


class VideoListSerializer(serializers.ModelSerializer):
    permission_classes = [AllowAny]

    class Meta:
        model = Video
        fields = ['id', 'title', 'slug', 'cover_image', 'duration_seconds']


class VideoDetailSerializer(serializers.ModelSerializer):
    permission_classes = [AllowAny]

    artists = ArtistBasicSerializer(many=True, read_only=True)
    more_from_artist = serializers.SerializerMethodField()
    similar_videos = serializers.SerializerMethodField()
    hls_file = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'slug', 'artists', 'era', 'recording_year',
            'duration_seconds', 'hls_file', 'cover_image', 'view_count', 'likes_count',
            'more_from_artist', 'similar_videos'
        ]

    def get_hls_file(self, obj):
        has_access = self.context.get('user_has_all_access', False)
        if has_access and obj.hls_file:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(settings.MEDIA_URL + obj.hls_file)
            return settings.MEDIA_URL + obj.hls_file
        return None


    def get_more_from_artist(self, obj):
        artist_ids = obj.artists.values_list('id', flat=True)
        if not artist_ids:
            return []
        videos = Video.objects.filter(
            status=PublishStatus.PUBLISHED,
            artists__in=artist_ids
        ).exclude(id=obj.id).distinct().order_by('-created_at')[:10]
        return VideoListSerializer(videos, many=True, context=self.context).data

    def get_similar_videos(self, obj):
        artist_ids = obj.artists.values_list('id', flat=True)
        videos = Video.objects.filter(
            status=PublishStatus.PUBLISHED
        ).exclude(
            artists__in=artist_ids
        ).distinct().order_by('?')[:10]
        return VideoListSerializer(videos, many=True, context=self.context).data
