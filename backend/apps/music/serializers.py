from rest_framework import serializers
from .models import Artist, Album, Track , Genre, Instrument , Label
from drf_spectacular.utils import extend_schema_field
from rest_framework.reverse import reverse


class ArtistSerializer(serializers.ModelSerializer):
    artist_type_display = serializers.CharField(source='get_artist_type_display', read_only=True)
    era_display = serializers.CharField(source='get_era_display', read_only=True)
    albums = serializers.SerializerMethodField()
    singles = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = [
            'name', 'slug', 'country','birth_year','death_year', 'artist_type', 'artist_type_display',
            'era', 'era_display', 'image', 'biography','likes_count','followers_count' , 'albums', 'singles'
        ]

    def get_albums(self, obj):
        albums = getattr(obj, 'prefetched_albums', [])
        return AlbumListSerializer(albums, many=True, context=self.context).data

    def get_singles(self, obj):
        singles = getattr(obj, 'prefetched_singles', [])
        return TrackSerializer(singles, many=True, context=self.context).data


class ArtistBasicSerializer(serializers.ModelSerializer):
    artist_type = serializers.CharField(source='get_artist_type_display', read_only=True)

    class Meta:
        model = Artist
        fields = ['name', 'slug','artist_type']



class RelatedArtistSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ["name", "slug"]



class TrackSerializer(serializers.ModelSerializer):
    artists = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            'id', 'title', 'album', 'artists', 'slug', 'cover_image',
            'duration_seconds', 'status', 'likes_count', 'audio_url', 'download_url'
        ]

    def get_artists(self, obj):
        track_artists = list(obj.artists.all())
        track_artist_ids = [artist.id for artist in track_artists]
        if obj.album:
            album_main_artists = obj.album.main_artists.all()
            for main_artist in reversed(list(album_main_artists)):
                if main_artist.id not in track_artist_ids:
                    track_artists.insert(0, main_artist)
        return ArtistBasicSerializer(track_artists, many=True, context=self.context).data

    def get_cover_image(self, obj):
        request = self.context.get('request')
        if obj.cover_image:
            return request.build_absolute_uri(obj.cover_image.url)
        elif obj.album and obj.album.cover_image:
            return request.build_absolute_uri(obj.album.cover_image.url)
        return None

    def get_audio_url(self, obj):
        has_stream_access = self.context.get("has_stream_access", False)
        if not has_stream_access or not obj.audio_file:
            return None
        request = self.context.get('request')
        if request:
            try:
                return reverse(
                    'track-stream',
                    kwargs={'slug': obj.slug},
                    request=request
                )
            except Exception:
                return None
        return None

    def get_download_url(self, obj):
        has_download_access = self.context.get("has_download_access", False)
        if not has_download_access or not obj.audio_file:
            return None
        request = self.context.get('request')
        if request:
            try:
                return reverse('track-download',kwargs={'slug': obj.slug},request=request)
            except Exception:
                return None
        return None

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
            'release_year', 'total_tracks'
        ]



class AlbumDetailSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    total_tracks = serializers.IntegerField(source='annotated_total_tracks', read_only=True)
    total_duration_ms = serializers.IntegerField(source='annotated_total_duration_ms', read_only=True)
    on_this_album = serializers.SerializerMethodField()
    main_artists = ArtistBasicSerializer(many=True, read_only=True)

    class Meta:
        model = Album
        fields = [
            'id', 'title', 'title_fa', 'slug', 'cover_image',
            'release_year', 'description', 'main_artists', 'on_this_album',
            'total_tracks', 'total_duration_ms', 'status', 'tracks'
        ]

    def get_on_this_album(self, obj):
        main_artists_ids = obj.main_artists.values_list('id', flat=True)
        track_artists_ids = obj.tracks.values_list('artists__id', flat=True)
        all_artist_ids = set(main_artists_ids) | set(track_artists_ids)
        all_artist_ids.discard(None)
        artists = Artist.objects.filter(id__in=all_artist_ids).distinct()
        serializer = ArtistBasicSerializer(artists, many=True, context=self.context)
        return serializer.data



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



class LabelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['name', 'slug', 'logo' , 'likes_count','followers_count']



class LabelDetailSerializer(serializers.ModelSerializer):
    albums_count = serializers.IntegerField(read_only=True)
    tracks_count = serializers.IntegerField(read_only=True)
    albums = serializers.SerializerMethodField()
    singles = serializers.SerializerMethodField()

    class Meta:
        model = Label
        fields = [
            'name', 'slug', 'logo', 'country', 'website', 'description',
            'albums_count', 'tracks_count', 'albums', 'singles'
        ]

    @extend_schema_field(AlbumListSerializer(many=True))
    def get_albums(self, obj):
        albums = obj.albums_by_label.all()
        return AlbumListSerializer(albums, many=True, context=self.context).data

    @extend_schema_field(TrackSerializer(many=True))
    def get_singles(self, obj):
        singles = getattr(obj, 'prefetched_singles', [])
        return TrackSerializer(singles, many=True, context=self.context).data
