from rest_framework import serializers
from .models import Artist, Album, Track


class ArtistSerializer(serializers.ModelSerializer):
    artist_type_display = serializers.CharField(source='get_artist_type_display', read_only=True)
    era_display = serializers.CharField(source='get_era_display', read_only=True)

    class Meta:
        model = Artist
        fields = [
            'id', 'name', 'slug', 'country', 'artist_type', 'artist_type_display',
            'era', 'era_display', 'image', 'biography'
        ]



class TrackSerializer(serializers.ModelSerializer):
    singer_name = serializers.CharField(source='singer.name', read_only=True)
    composer_name = serializers.CharField(source='composer.name', read_only=True)
    is_single = serializers.BooleanField(read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            'id', 'title', 'slug', 'audio_file', 'cover_image', 'release_date',
            'track_number', 'duration_ms', 'duration_seconds', 'instrument',
            'composer', 'composer_name', 'singer', 'singer_name', 'is_single', 'status'
        ]

    def get_duration_seconds(self, obj):
        if not obj.duration_ms:
            return "00:00"
        seconds = obj.duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"



class AlbumListSerializer(serializers.ModelSerializer):
    total_tracks = serializers.IntegerField(read_only=True)

    class Meta:
        model = Album
        fields = [
            'id', 'title', 'slug', 'cover_image', 'composer',
            'release_date', 'total_tracks', 'status'
        ]



class AlbumDetailSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)

    total_tracks = serializers.IntegerField(read_only=True)
    total_duration_ms = serializers.IntegerField(read_only=True)
    on_this_album = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Album
        fields = [
            'id', 'title', 'slug', 'cover_image', 'release_date',
            'composer', 'conductor', 'orchestra', 'soloist', 'ensemble',
            'on_this_album', 'total_tracks', 'total_duration_ms', 'status',
            'tracks'
        ]
