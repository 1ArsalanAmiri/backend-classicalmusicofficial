from rest_framework import serializers
from .models import PlaylistTrack, Playlist
from apps.music.serializers import TrackSerializer


class PlaylistTrackSerializer(serializers.ModelSerializer):
    track = TrackSerializer(read_only=True)

    class Meta:
        model = PlaylistTrack
        fields = ["id", "track", "order", "added_at"]


class PlaylistListSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    owner_phone_number = serializers.CharField(source="owner.phone_number", read_only=True)

    class Meta:
        model = Playlist
        fields = [
            "id",
            "slug",
            "title",
            "owner_username",
            "owner_phone_number",
            "cover_image",
            "is_public",
            "total_tracks",
            "total_duration_ms",
            "created_at",
        ]


class PlaylistDetailSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    tracks = PlaylistTrackSerializer(
        source="playlist_tracks",
        many=True,
        read_only=True
    )

    class Meta:
        model = Playlist
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "owner_username",
            "cover_image",
            "is_public",
            "total_tracks",
            "total_duration_ms",
            "created_at",
            "updated_at",
            "tracks",
        ]


class PlaylistCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = ["title", "description", "cover_image", "is_public","track_slug"]
