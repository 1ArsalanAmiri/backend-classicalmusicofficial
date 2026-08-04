from rest_framework import serializers
from .models import Playlist, PlaylistItem
from apps.music.serializers import TrackSerializer
from apps.music.models import Track
from django.db.models import Sum


class PlaylistItemSerializer(serializers.ModelSerializer):
    track = TrackSerializer(read_only=True)

    class Meta:
        model = PlaylistItem
        fields = ['id', 'track', 'order', 'created_at']


class PlaylistListSerializer(serializers.ModelSerializer):
    tracks_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = Playlist
        fields = [
            'id', 'title', 'slug', 'description', 'cover_image',
            'is_public', 'tracks_count', 'created_at'
        ]


class PlaylistDetailSerializer(serializers.ModelSerializer):
    items = PlaylistItemSerializer(many=True, read_only=True)
    tracks_count = serializers.IntegerField(source='items.count', read_only=True)
    total_duration_ms = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [
            'id', 'title', 'slug', 'description', 'cover_image',
            'is_public', 'tracks_count', 'total_duration_ms', 'created_at', 'items'
        ]

    def get_total_duration_ms(self, obj):
        return obj.tracks.aggregate(total=Sum('duration_ms'))['total'] or 0


class PlaylistCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = ['title', 'description', 'cover_image', 'is_public']


class TrackActionSerializer(serializers.Serializer):
    track_id = serializers.IntegerField(required=True)