from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from django.db.models.functions import Greatest
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q
from apps.music.models import Track, Album, Artist, Label
from apps.music.serializers import TrackSerializer, AlbumListSerializer, ArtistSerializer, LabelListSerializer

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes




class GlobalSearchView(APIView):

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Search",
        parameters=[
            OpenApiParameter(
                name='q',
                description='Search query (2 minimum)',
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='limit',
                description='Results per page(Default 10,Maximum 20)',
                required=False,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
        ]
    )
    @method_decorator(cache_page(60 * 2))
    def get(self, request):
        query = request.query_params.get('q', '').strip()

        try:
            limit = int(request.query_params.get('limit', 5))
            limit = min(limit, 20)
        except ValueError:
            limit = 5

        if len(query) < 2:
            return Response({
                "tracks": [],
                "albums": [],
                "artists": [],
                "labels": []
            })

        search_query = SearchQuery(query)

        track_vector = SearchVector('title', weight='A') + SearchVector('singer__name', weight='B')

        tracks = Track.objects.select_related('singer', 'album', 'label').prefetch_related('genre').annotate(
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

        labels = Label.objects.annotate(
            similarity=TrigramSimilarity('name', query)
        ).filter(
            similarity__gt=0.2
        ).order_by('-similarity')[:limit]

        return Response({
            "tracks": TrackSerializer(tracks, many=True, context={'request': request}).data,
            "albums": AlbumListSerializer(albums, many=True, context={'request': request}).data,
            "artists": ArtistSerializer(artists, many=True, context={'request': request}).data,
            "labels": LabelListSerializer(labels, many=True, context={'request': request}).data,
        })
