from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models.functions import Greatest, Coalesce
from django.db.models import Q, Case, When, Value, IntegerField
from rest_framework import generics
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from apps.music.models import Track, Album, Artist, AlbumType
from apps.music.serializers import TrackSerializer, LandingAlbumSerializer
from apps.videos.models import Video
from apps.videos.serializers import LandingVideoSerializer
from apps.content.models import Post
from apps.content.serializers import LandingPostSerializer
from apps.common.models import PublishStatus
from apps.common.permissions import HasAllSubscription
from apps.subscriptions.services import user_has_stream_access, user_has_all_access


DEFAULT_LIMIT = 5
MAX_LIMIT = 20
RANK_THRESHOLD = 0.1
SIMILARITY_THRESHOLD = 0.2
ARTIST_FANOUT_CAP = 100

SEARCH_CATEGORIES = {'album', 'playlist', 'video', 'article', 'track'}


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


class SearchResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CategorySearchView(generics.ListAPIView):
    pagination_class = SearchResultsPagination
    permission_classes = [AllowAny]
    filter_backends = []

    def _get_query_and_category(self):
        query = self.request.query_params.get('q', '').strip().lower()
        category = self.request.query_params.get('type', '').strip().lower()
        return query, category

    @extend_schema(
        summary="Category Search",
        parameters=[
            OpenApiParameter(
                name='q', required=True,
                type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='type', description=f"دسته: {' | '.join(sorted(SEARCH_CATEGORIES))}", required=True,
                type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page', required=False,
                type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size', required=False,
                type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Search'],
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_serializer_class(self):
        _, category = self._get_query_and_category()
        return {
            'track': TrackSerializer,
            'album': LandingAlbumSerializer,
            'playlist': LandingAlbumSerializer,
            'video': LandingVideoSerializer,
            'article': LandingPostSerializer,
        }.get(category, TrackSerializer)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        _, category = self._get_query_and_category()
        request = self.request

        if category == 'track':
            if request.user.is_authenticated:
                context['has_stream_access'] = user_has_stream_access(request.user)
                context['has_download_access'] = user_has_all_access(request.user)
            else:
                context['has_stream_access'] = False
                context['has_download_access'] = False

        elif category == 'video':
            if request.user.is_authenticated:
                context['has_all_access'] = user_has_all_access(request.user)
            else:
                context['has_all_access'] = False

        return context

    def _matched_artist_ids(self, query):
        return list(
            Artist.objects.annotate(
                similarity=Greatest(
                    TrigramSimilarity('name', query),
                    Coalesce(TrigramSimilarity('nickname', query), 0.0),
                )
            ).filter(
                similarity__gt=SIMILARITY_THRESHOLD
            ).order_by('-similarity').values_list('id', flat=True)[:ARTIST_FANOUT_CAP]
        )

    def get_queryset(self):
        query, category = self._get_query_and_category()

        if category not in SEARCH_CATEGORIES:
            raise ValidationError({
                'type': f"مقدار type باید یکی از این‌ها باشه: {', '.join(sorted(SEARCH_CATEGORIES))}"
            })

        if len(query) < 2:
            raise ValidationError({'q': 'عبارت جستجو باید حداقل ۲ کاراکتر باشد.'})

        search_query = SearchQuery(query, config='simple', search_type='websearch')

        if category in ('album', 'playlist'):
            album_type = AlbumType.OFFICIAL if category == 'album' else AlbumType.EDITORIAL_PLAYLIST
            matched_artist_ids = self._matched_artist_ids(query)
            return Album.objects.filter(
                status=PublishStatus.PUBLISHED,
                album_type=album_type,
            ).prefetch_related('main_artists').annotate(
                rank=SearchRank('search_vector', search_query),
                similarity=TrigramSimilarity('title', query),
            ).filter(
                Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gt=SIMILARITY_THRESHOLD) |
                Q(main_artists__id__in=matched_artist_ids)
            ).distinct().order_by('-rank', '-similarity', '-id')

        if category == 'track':
            matched_artist_ids = self._matched_artist_ids(query)
            return Track.objects.filter(
                status=PublishStatus.PUBLISHED,
            ).select_related('album').prefetch_related(
                'artists', 'album__main_artists'
            ).annotate(
                rank=SearchRank('search_vector', search_query),
                similarity=TrigramSimilarity('title', query),
            ).filter(
                Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gt=SIMILARITY_THRESHOLD) |
                Q(artists__id__in=matched_artist_ids) | Q(album__main_artists__id__in=matched_artist_ids)
            ).distinct().order_by('-rank', '-similarity', '-id')

        if category == 'video':
            return Video.objects.filter(
                status=PublishStatus.PUBLISHED,
            ).prefetch_related('artists').annotate(
                similarity=TrigramSimilarity('title', query),
            ).filter(similarity__gt=SIMILARITY_THRESHOLD).order_by('-similarity', '-id')

        return Post.objects.filter(
            is_published=True,
            title__icontains=query,
        ).order_by('-created_at')
