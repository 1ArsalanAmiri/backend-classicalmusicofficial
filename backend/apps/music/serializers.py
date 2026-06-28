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
            'name', 'slug', 'country', 'artist_type', 'artist_type_display',
            'era', 'era_display', 'image', 'biography','likes_count','followers_count'
        ]



class ArtistBasicSerializer(serializers.ModelSerializer):
    artist_type_display = serializers.CharField(source='get_artist_type_display', read_only=True)

    class Meta:
        model = Artist
        fields = ['name', 'slug', 'image', 'artist_type_display']



class LabelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['name', 'slug', 'logo' , 'likes_count','followers_count']



class LabelDetailSerializer(serializers.ModelSerializer):
    albums_count = serializers.IntegerField(read_only=True)
    tracks_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Label
        fields = ['name', 'slug', 'logo', 'country', 'website', 'description', 'albums_count', 'tracks_count']



class RelatedArtistSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ["name", "slug"]



class TrackSerializer(serializers.ModelSerializer):
    artists = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            'id', 'title', 'album', 'artists', 'slug', 'cover_image',
            'duration_seconds', 'status', 'likes_count', 'audio_url'
        ]

    def get_artists(self, obj):
        track_artists = list(obj.artists.all())
        album_artist = obj.album.artist if obj.album else None
        if album_artist:
            if album_artist not in track_artists:
                track_artists.insert(0, album_artist)
        return ArtistBasicSerializer(track_artists, many=True, context=self.context).data


    def get_cover_image(self, obj):
        request = self.context.get('request')
        if obj.cover_image:
            return request.build_absolute_uri(obj.cover_image.url)
        elif obj.album and obj.album.cover_image:
            return request.build_absolute_uri(obj.album.cover_image.url)
        return None


    def get_audio_stream_url(self, obj):
        has_stream_access = self.context.get("has_stream_access", False)
        has_download_access = self.context.get("has_download_access", False)
        if not has_stream_access or has_download_access:
            return None
        request = self.context.get('request')
        if request is None:
            return None
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
            'title', 'slug', 'cover_image',
            'release_date', 'total_tracks'
        ]



class AlbumDetailSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    total_tracks = serializers.IntegerField(read_only=True)
    total_duration_ms = serializers.IntegerField(read_only=True)
    on_this_album = serializers.SerializerMethodField()
    main_artist = ArtistBasicSerializer(source='artist', read_only=True)

    class Meta:
        model = Album
        fields = [
            'id', 'title', 'title_fa', 'slug', 'cover_image',
            'release_date', 'main_artist', 'on_this_album',
            'total_tracks', 'total_duration_ms', 'status', 'tracks'
        ]

    def get_on_this_album(self, obj):
        unique_artists = {}
        for track in obj.tracks.all():
            for artist in track.artists.all():
                if artist.id not in unique_artists:
                    unique_artists[artist.id] = artist
        for credit in obj.credits.all():
            if credit.artist.id not in unique_artists:
                unique_artists[credit.artist.id] = credit.artist
        if obj.artist and obj.artist.id in unique_artists:
            del unique_artists[obj.artist.id]
        return ArtistBasicSerializer(unique_artists.values(), many=True, context=self.context).data



class GenreSerializer(serializers.ModelSerializer):
    track_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Genre
        fields = ['name', 'slug', 'track_count']



class InstrumentSerializer(serializers.ModelSerializer):
    track_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Instrument
        fields = ['name', 'slug', 'track_count']
