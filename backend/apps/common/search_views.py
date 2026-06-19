from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from apps.music.models import Track,Album,Artist
from apps.music.serializers import TrackSerializer, AlbumListSerializer, ArtistSerializer

class GlobalSearchView(APIView):
    
    permission_classes = [AllowAny]

    @method_decorator(cache_page(60 * 2))
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()

        if not query or len(query) < 2:
            return Response({
                "tracks": [],
                "albums": [],
                "artists": []
            })

        limit = 5

        tracks = Track.objects.select_related('singer', 'album', 'genre', 'label').filter(
            Q(title__icontains=query) |
            Q(singer__name__icontains=query) |
            Q(composer__name__icontains=query)
        ).filter(status='published')[:limit]

        albums = Album.objects.select_related('composer', 'label').filter(
            Q(title__icontains=query) |
            Q(composer__name__icontains=query)
        ).filter(status='published')[:limit]

        artists = Artist.objects.filter(
            Q(name__icontains=query)
        )[:limit]

        track_data = TrackSerializer(tracks, many=True, context={'request': request}).data
        album_data = AlbumListSerializer(albums, many=True, context={'request': request}).data
        artist_data = ArtistSerializer(artists, many=True, context={'request': request}).data

        return Response({
            "tracks": track_data,
            "albums": album_data,
            "artists": artist_data
        })
