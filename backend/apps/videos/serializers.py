from django.conf import settings
from rest_framework import serializers
from .models import Video, PublishStatus
from ..music.serializers import ArtistBasicSerializer


class VideoListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['id', 'title', 'slug', 'cover_image', 'duration_seconds']


class VideoDetailSerializer(serializers.ModelSerializer):
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
        has_access = self.context.get('has_all_access', False)
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


class LandingVideoSerializer(serializers.ModelSerializer):
    artists = ArtistBasicSerializer(many=True, read_only=True)
    era_display = serializers.CharField(source='get_era_display', read_only=True)
    video_file = serializers.SerializerMethodField()
    hls_file = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'slug', 'artists', 'era', 'era_display',
            'recording_year', 'duration_seconds', 'cover_image',
            'video_file', 'hls_file', 'status', 'view_count',
            'likes_count', 'created_at', 'updated_at',
        ]

    def get_hls_file(self, obj):
        has_access = self.context.get('has_all_access', False)
        if has_access and obj.hls_file:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(settings.MEDIA_URL + obj.hls_file)
            return settings.MEDIA_URL + obj.hls_file
        return None

    def get_video_file(self, obj):
        has_access = self.context.get('has_all_access', False)
        if not has_access or not obj.video_file:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.video_file.url)
        return obj.video_file.url