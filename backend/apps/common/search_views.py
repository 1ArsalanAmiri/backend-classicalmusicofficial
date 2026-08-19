from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models.functions import Greatest, Coalesce
from django.db.models import Q, Count
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
SIMILARITY_THRESHOLD = 0.2
ARTIST_FANOUT_CAP = 50


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
        description="Search across tracks, albums, artists and labels using full-text search with trigram fallback.",
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

        search_query = SearchQuery(query, config='simple', search_type='websearch')

        # --- ۱. آرتیست‌ها (trigram روی name + nickname) ---
        artist_qs = Artist.objects.annotate(
            similarity=Greatest(
                TrigramSimilarity('name', query),
                Coalesce(TrigramSimilarity('nickname', query), 0.0),
            )
        ).filter(similarity__gt=SIMILARITY_THRESHOLD).order_by('-similarity', '-id')

        artists = list(artist_qs[:limit])
        # ست جدا و بزرگ‌تر، فقط برای فیلتر کردن ترک/آلبوم بر اساس آرتیست match‌شده
        matched_artist_ids = list(artist_qs.values_list('id', flat=True)[:ARTIST_FANOUT_CAP])

        # --- ۲. لیبل‌ها (trigram روی name) ---
        labels = Label.objects.annotate(
            similarity=TrigramSimilarity('name', query)
        ).filter(similarity__gt=SIMILARITY_THRESHOLD).order_by('-similarity', '-id')[:limit]

        # --- ۳. آلبوم‌ها: تطبیق عنوان (FTS + trigram) یا تطبیق آرتیست اصلی ---
        album_title_matches = Album.objects.filter(status=PublishStatus.PUBLISHED).annotate(
            rank=SearchRank('search_vector', search_query),
            similarity=TrigramSimilarity('title', query),
            annotated_total_tracks=Count('tracks', distinct=True),
        ).filter(
            Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gt=SIMILARITY_THRESHOLD)
        ).order_by('-rank', '-similarity', '-id')[:limit]

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

        # --- ۴. ترک‌ها: تطبیق عنوان (FTS + trigram) یا تطبیق آرتیست ---
        track_title_matches = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related(
            'album'
        ).prefetch_related('artists', 'album__main_artists').annotate(
            rank=SearchRank('search_vector', search_query),
            similarity=TrigramSimilarity('title', query),
        ).filter(
            Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gt=SIMILARITY_THRESHOLD)
        ).order_by('-rank', '-similarity', '-id')[:limit]

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