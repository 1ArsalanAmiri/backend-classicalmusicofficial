from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q

from apps.music.models import Track, Album, Artist
from apps.music.serializers import TrackSerializer, AlbumListSerializer, ArtistSerializer


class GlobalSearchView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(cache_page(60 * 2))
    def get(self, request):
        query = request.query_params.get('q', '').strip()

        if len(query) < 2:
            return Response({"tracks": [], "albums": [], "artists": []})

        limit = 5
        search_query = SearchQuery(query)

        track_vector = SearchVector('title', weight='A') + SearchVector('singer__name', weight='B')

        tracks = Track.objects.select_related('singer', 'album', 'genre', 'label').annotate(
            rank=SearchRank(track_vector, search_query),
            similarity=Greatest(
                TrigramSimilarity('title', query),
                TrigramSimilarity('singer__name', query)
            )
        ).filter(
            Q(rank__gte=0.1) | Q(similarity__gt=0.2),
            status='published'
        ).order_by('-rank', '-similarity')[:limit]

        album_vector = SearchVector('title', weight='A') + SearchVector('composer', weight='B')

        albums = Album.objects.select_related('label').annotate(
            rank=SearchRank(album_vector, search_query),
            similarity=TrigramSimilarity('title', query)
        ).filter(
            Q(rank__gte=0.1) | Q(similarity__gt=0.2),
            status='published'
        ).order_by('-rank', '-similarity')[:limit]

        artists = Artist.objects.annotate(
            similarity=TrigramSimilarity('name', query)
        ).filter(
            similarity__gt=0.2
        ).order_by('-similarity')[:limit]

        return Response({
            "tracks": TrackSerializer(tracks, many=True, context={'request': request}).data,
            "albums": AlbumListSerializer(albums, many=True, context={'request': request}).data,
            "artists": ArtistSerializer(artists, many=True, context={'request': request}).data,
        })
