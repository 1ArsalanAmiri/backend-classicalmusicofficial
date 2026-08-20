from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramWordSimilarity
from django.db.models.functions import Greatest, Coalesce
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from apps.music.models import Track, Album, Artist, Label
from apps.music.serializers import TrackSerializer, AlbumListSerializer, ArtistSerializer, LabelListSerializer
from apps.common.models import PublishStatus

from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes

DEFAULT_LIMIT = 5
MAX_LIMIT = 20
RANK_THRESHOLD = 0.1
ARTIST_FANOUT_CAP = 50


def get_similarity_threshold(query: str) -> float:

    length = len(query)
    if length <= 3:
        return 0.15
    if length <= 6:
        return 0.25
    return 0.3


def _starts_with_boost(field: str, query: str):

    return Case(
        When(**{f'{field}__istartswith': query}, then=Value(2)),
        When(**{f'{field}__icontains': query}, then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def _merge_unique(primary, secondary, limit):
    seen_ids = set()
    result = []
    for obj in list(primary):
        if obj.id not in seen_ids:
            seen_ids.add(obj.id)
            result.append(obj)
    for obj in secondary:
        if len(result) >= limit:
            break
        if obj.id not in seen_ids:
            seen_ids.add(obj.id)
            result.append(obj)
    return result[:limit]


class GlobalSearchView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Global Search",
        description="Search across tracks, albums, artists and labels using full-text search with trigram + prefix fallback.",
        parameters=[
            OpenApiParameter(
                name='q',
                description='Search query (2 characters minimum)',
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='limit',
                description=f'Results per group (Default {DEFAULT_LIMIT}, Maximum {MAX_LIMIT})',
                required=False,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            200: inline_serializer(
                name='GlobalSearchResponse',
                fields={
                    'tracks': TrackSerializer(many=True),
                    'albums': AlbumListSerializer(many=True),
                    'artists': ArtistSerializer(many=True),
                    'labels': LabelListSerializer(many=True),
                }
            ),
        },
        tags=['Search'],
    )
    @method_decorator(cache_page(60 * 2))
    def get(self, request):
        query = request.query_params.get('q', '').strip().lower()

        try:
            limit = int(request.query_params.get('limit', DEFAULT_LIMIT))
            limit = max(1, min(limit, MAX_LIMIT))
        except ValueError:
            limit = DEFAULT_LIMIT

        if len(query) < 2:
            return Response({"tracks": [], "albums": [], "artists": [], "labels": []})

        similarity_threshold = get_similarity_threshold(query)
        search_query = SearchQuery(query, config='simple', search_type='websearch')


        artist_qs = Artist.objects.annotate(
            similarity=Greatest(
                TrigramWordSimilarity(query, 'name'),
                Coalesce(TrigramWordSimilarity(query, 'nickname'), 0.0),
            ),
            starts_with_boost=Greatest(
                _starts_with_boost('name', query),
                _starts_with_boost('nickname', query),
            ),
        ).filter(
            Q(name__icontains=query) |
            Q(nickname__icontains=query) |
            Q(similarity__gte=similarity_threshold)
        ).order_by('-starts_with_boost', '-similarity', '-id')

        artists = list(artist_qs[:limit])
        matched_artist_ids = list(artist_qs.values_list('id', flat=True)[:ARTIST_FANOUT_CAP])

        # --- ۲. لیبل‌ها ---
        labels = Label.objects.annotate(
            similarity=TrigramWordSimilarity(query, 'name'),
            starts_with_boost=_starts_with_boost('name', query),
        ).filter(
            Q(name__icontains=query) | Q(similarity__gte=similarity_threshold)
        ).order_by('-starts_with_boost', '-similarity', '-id')[:limit]

        album_title_matches = Album.objects.filter(status=PublishStatus.PUBLISHED).annotate(
            rank=SearchRank('search_vector', search_query),
            similarity=Greatest(
                TrigramWordSimilarity(query, 'title'),
                Coalesce(TrigramWordSimilarity(query, 'title_fa'), 0.0),
            ),
            starts_with_boost=Greatest(
                _starts_with_boost('title', query),
                _starts_with_boost('title_fa', query),
            ),
            annotated_total_tracks=Count('tracks', distinct=True),
        ).filter(
            Q(rank__gte=RANK_THRESHOLD) |
            Q(similarity__gte=similarity_threshold) |
            Q(title__icontains=query) |
            Q(title_fa__icontains=query)
        ).order_by('-starts_with_boost', '-rank', '-similarity', '-id')[:limit]

        albums_by_artist = []
        if matched_artist_ids:
            albums_by_artist = list(
                Album.objects.filter(
                    status=PublishStatus.PUBLISHED,
                    main_artists__id__in=matched_artist_ids,
                ).annotate(
                    annotated_total_tracks=Count('tracks', distinct=True),
                ).distinct().order_by('-release_year')[:limit]
            )

        albums = _merge_unique(album_title_matches, albums_by_artist, limit)

        track_title_matches = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related(
            'album'
        ).prefetch_related('artists', 'album__main_artists').annotate(
            rank=SearchRank('search_vector', search_query),
            similarity=TrigramWordSimilarity(query, 'title'),
            starts_with_boost=_starts_with_boost('title', query),
        ).filter(
            Q(rank__gte=RANK_THRESHOLD) |
            Q(similarity__gte=similarity_threshold) |
            Q(title__icontains=query)
        ).order_by('-starts_with_boost', '-rank', '-similarity', '-id')[:limit]

        tracks_by_artist = []
        if matched_artist_ids:
            tracks_by_artist = list(
                Track.objects.filter(
                    Q(artists__id__in=matched_artist_ids) | Q(album__main_artists__id__in=matched_artist_ids),
                    status=PublishStatus.PUBLISHED,
                ).select_related('album').prefetch_related(
                    'artists', 'album__main_artists'
                ).distinct().order_by('-created_at')[:limit]
            )

        tracks = _merge_unique(track_title_matches, tracks_by_artist, limit)

        return Response({
            "tracks": TrackSerializer(tracks, many=True, context={'request': request}).data,
            "albums": AlbumListSerializer(albums, many=True, context={'request': request}).data,
            "artists": ArtistSerializer(artists, many=True, context={'request': request}).data,
            "labels": LabelListSerializer(labels, many=True, context={'request': request}).data,
        })