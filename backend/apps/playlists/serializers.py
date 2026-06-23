from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import PlaylistTrack, Playlist
from apps.music.serializers import TrackSerializer
from apps.music.models import Track


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
    track_slug = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Playlist
        fields = ["track_slug", "title", "description", "cover_image", "is_public"]

    def create(self, validated_data):
        track_slug = validated_data.pop('track_slug', None)

        playlist = super().create(validated_data)

        if track_slug:
            try:
                track = Track.objects.get(slug=track_slug)
                PlaylistTrack.objects.create(
                    playlist=playlist,
                    track=track,
                    order=1
                )
            except Track.DoesNotExist:
                raise ValidationError({"track_slug": "ترک با این شناسه یافت نشد."})

        return playlist