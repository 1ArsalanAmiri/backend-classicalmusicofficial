from django.urls import reverse
from rest_framework import serializers
from .models import Artist, Album, Track,Genre, Instrument , Label , PlayHistory
from drf_spectacular.utils import extend_schema_field


class ArtistSerializer(serializers.ModelSerializer):
    artist_type_display = serializers.CharField(source='get_artist_type_display', read_only=True)
    era_display = serializers.CharField(source='get_era_display', read_only=True)

    class Meta:
        model = Artist
        fields = [
            'id', 'name', 'slug', 'country', 'artist_type', 'artist_type_display',
            'era', 'era_display', 'image', 'biography','likes_count','followers_count'
        ]



class LabelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'name', 'slug', 'logo' , 'likes_count','followers_count']



class LabelDetailSerializer(serializers.ModelSerializer):
    albums_count = serializers.IntegerField(read_only=True)
    tracks_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Label
        fields = ['id', 'name', 'slug', 'logo', 'country', 'website', 'description', 'albums_count', 'tracks_count']



class RelatedArtistSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ["id", "name", "slug", "image"]


class TrackSerializer(serializers.ModelSerializer):
    instrument_name = serializers.CharField(source='instrument.name', read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    audio_stream_url = serializers.SerializerMethodField()
    artists = RelatedArtistSerializer(many=True, read_only=True)

    class Meta:
        model = Track
        fields = [
            'id', 'title', 'album', 'artists', 'slug', 'audio_stream_url', 'cover_image', 'release_date',
            'duration_seconds', 'instrument_name', 'status', 'likes_count'
        ]


    def get_audio_stream_url(self, obj):
        has_stream_access = self.context.get("has_stream_access", False)
        has_download_access = self.context.get("has_download_access", False)

        if not has_stream_access or has_download_access:
            return None
        request = self.context.get('request')
        if request is None:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(reverse('track-stream', kwargs={'slug': obj.slug}))

    @extend_schema_field(serializers.IntegerField())
    def get_duration_seconds(self, obj):
        if not obj.duration_ms:
            return 0
        return obj.duration_ms // 1000


class AlbumListSerializer(serializers.ModelSerializer):
    total_tracks = serializers.IntegerField(read_only=True)

    class Meta:
        model = Album
        fields = [
            'id', 'title', 'slug', 'cover_image',
            'release_date', 'total_tracks'
        ]


class AlbumDetailSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    total_tracks = serializers.IntegerField(read_only=True)
    total_duration_ms = serializers.IntegerField(read_only=True)
    main_artist = RelatedArtistSerializer(source='artist', read_only=True)
    on_this_album = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = [
            'id', 'title', 'title_fa', 'slug', 'cover_image', 'release_date',
            'main_artist', 'on_this_album', 'total_tracks', 'total_duration_ms', 'status',
            'tracks', 'likes_count', 'comments_count',
        ]


    @extend_schema_field(RelatedArtistSerializer(many=True))
    def get_on_this_album(self, obj):
        artists = obj.on_this_album
        return RelatedArtistSerializer(artists, many=True, context=self.context).data


class GenreSerializer(serializers.ModelSerializer):
    track_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Genre
        fields = ['id', 'name', 'slug', 'track_count']



class InstrumentSerializer(serializers.ModelSerializer):
    track_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Instrument
        fields = ['id', 'name', 'slug', 'track_count']
