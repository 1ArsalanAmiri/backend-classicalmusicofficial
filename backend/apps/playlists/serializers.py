from rest_framework import serializers
from .models import Playlist, PlaylistItem
from apps.music.serializers import TrackSerializer


class PlaylistItemSerializer(serializers.ModelSerializer):
    track = TrackSerializer(read_only=True)

    class Meta:
        model = PlaylistItem
        fields = ['id', 'track', 'order', 'created_at']


class PlaylistListSerializer(serializers.ModelSerializer):
    tracks_count = serializers.IntegerField(source='annotated_total_tracks', read_only=True, default=0)
    total_duration_ms = serializers.IntegerField(source='annotated_total_duration_ms', read_only=True, default=0)
    owner_username = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = Playlist
        fields = [
            'id', 'title', 'title_fa', 'slug', 'description', 'cover_image',
            'owner_username', 'tracks_count', 'total_duration_ms', 'created_at'
        ]


class PlaylistDetailSerializer(serializers.ModelSerializer):
    items = PlaylistItemSerializer(many=True, read_only=True)
    tracks_count = serializers.IntegerField(source='annotated_total_tracks', read_only=True, default=0)
    total_duration_ms = serializers.IntegerField(source='annotated_total_duration_ms', read_only=True, default=0)
    owner_username = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = Playlist
        fields = [
            'id', 'title', 'title_fa', 'slug', 'description', 'cover_image',
            'owner_username', 'tracks_count', 'total_duration_ms', 'created_at', 'items'
        ]


class PlaylistCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = ['title', 'title_fa', 'description', 'cover_image']


class TrackActionSerializer(serializers.Serializer):
    track_id = serializers.IntegerField(required=True, help_text="شناسه ترک مورد نظر")