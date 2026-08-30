from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models.functions import Greatest, Coalesce
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.music.models import Track, Album, Artist, AlbumType
from apps.music.serializers import TrackSerializer, LandingAlbumSerializer, ArtistBasicSerializer
from apps.videos.models import Video
from apps.videos.serializers import LandingVideoSerializer
from apps.content.models import Post
from apps.content.serializers import LandingPostSerializer
from apps.common.models import PublishStatus
from apps.subscriptions.services import user_has_stream_access, user_has_all_access

MIN_QUERY_LENGTH = 3

DEFAULT_GLOBAL_LIMIT = 5
MAX_GLOBAL_LIMIT = 20

RANK_THRESHOLD = 0.1
ARTIST_FANOUT_CAP = 100

SINGLE_CATEGORIES = ('album', 'playlist', 'track', 'video', 'article', 'artist')


def get_similarity_threshold(query: str) -> float:
    length = len(query)
    if length <= 4:
        return 0.1
    if length <= 6:
        return 0.15
    return 0.2


class SearchResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class BaseSearchMixin:

    def _validate_query(self, query):
        if len(query) < MIN_QUERY_LENGTH:
            raise ValidationError({'q': f'عبارت جستجو باید حداقل {MIN_QUERY_LENGTH} کاراکتر باشد.'})

    def _matched_artist_ids(self, query):
        threshold = get_similarity_threshold(query)
        return list(
            Artist.objects.annotate(
                similarity=Greatest(
                    TrigramSimilarity('name', query),
                    Coalesce(TrigramSimilarity('nickname', query), 0.0),
                )
            ).filter(
                similarity__gt=threshold
            ).order_by('-similarity').values_list('id', flat=True)[:ARTIST_FANOUT_CAP]
        )

    def _serializer_class_for(self, category):
        return {
            'track': TrackSerializer,
            'album': LandingAlbumSerializer,
            'playlist': LandingAlbumSerializer,
            'video': LandingVideoSerializer,
            'article': LandingPostSerializer,
            'artist': ArtistBasicSerializer,
        }[category]

    def _context_for(self, request, category):
        context = {'request': request}

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

    def _build_queryset(self, query, category, matched_artist_ids=None):
        search_query = SearchQuery(query, config='simple', search_type='websearch')
        similarity_threshold = get_similarity_threshold(query)

        if category in ('album', 'playlist'):
            album_type = AlbumType.OFFICIAL if category == 'album' else AlbumType.EDITORIAL_PLAYLIST
            return Album.objects.filter(
                status=PublishStatus.PUBLISHED,
                album_type=album_type,
            ).prefetch_related('main_artists').annotate(
                rank=SearchRank('search_vector', search_query),
                similarity=TrigramSimilarity('title', query),
            ).filter(
                Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gt=similarity_threshold) |
                Q(main_artists__id__in=matched_artist_ids or [])
            ).distinct().order_by('-rank', '-similarity', '-id')

        if category == 'track':
            return Track.objects.filter(
                status=PublishStatus.PUBLISHED,
            ).select_related('album').prefetch_related(
                'artists', 'album__main_artists'
            ).annotate(
                rank=SearchRank('search_vector', search_query),
                similarity=TrigramSimilarity('title', query),
            ).filter(
                Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gt=similarity_threshold) |
                Q(artists__id__in=matched_artist_ids or []) | Q(album__main_artists__id__in=matched_artist_ids or [])
            ).distinct().order_by('-rank', '-similarity', '-id')

        if category == 'video':
            return Video.objects.filter(
                status=PublishStatus.PUBLISHED,
            ).prefetch_related('artists').annotate(
                similarity=TrigramSimilarity('title', query),
            ).filter(similarity__gt=similarity_threshold).order_by('-similarity', '-id')

        if category == 'artist':
            return Artist.objects.annotate(
                similarity=Greatest(
                    TrigramSimilarity('name', query),
                    Coalesce(TrigramSimilarity('nickname', query), 0.0),
                )
            ).filter(similarity__gt=similarity_threshold).order_by('-similarity', '-id')

        return Post.objects.filter(
            is_published=True,
            title__icontains=query,
        ).order_by('-created_at')


class GlobalSearchView(BaseSearchMixin, APIView):
    permission_classes = [AllowAny]

    def _get_limit(self, request):
        try:
            limit = int(request.query_params.get('limit', DEFAULT_GLOBAL_LIMIT))
        except ValueError:
            limit = DEFAULT_GLOBAL_LIMIT
        return max(1, min(limit, MAX_GLOBAL_LIMIT))

    @extend_schema(
        summary="Global Search",
        parameters=[
            OpenApiParameter(
                name='q', description=f'عبارت جستجو (حداقل {MIN_QUERY_LENGTH} کاراکتر)', required=True,
                type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='limit',
                required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Search'],
    )
    def get(self, request):
        query = request.query_params.get('q', '').strip().lower()
        self._validate_query(query)

        limit = self._get_limit(request)
        matched_artist_ids = self._matched_artist_ids(query)

        results = {}
        for category in SINGLE_CATEGORIES:
            qs = self._build_queryset(query, category, matched_artist_ids)[:limit]
            serializer_class = self._serializer_class_for(category)
            context = self._context_for(request, category)
            results[category] = serializer_class(qs, many=True, context=context).data

        return Response({'query': query, 'results': results})


class CategorySearchView(BaseSearchMixin, generics.ListAPIView):
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
                name='q', description=f'عبارت جستجو (حداقل {MIN_QUERY_LENGTH} کاراکتر)', required=True,
                type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='type', description=f"دسته: {' | '.join(SINGLE_CATEGORIES)}", required=True,
                type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size', required=False,
                type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
            ),
        ],
        tags=['Search'],
    )
    def get(self, request, *args, **kwargs):
        query, category = self._get_query_and_category()

        if category not in SINGLE_CATEGORIES:
            raise ValidationError({
                'type': f"مقدار type باید یکی از این‌ها باشه: {', '.join(SINGLE_CATEGORIES)}"
            })
        self._validate_query(query)

        return self.list(request, *args, **kwargs)

    def get_serializer_class(self):
        _, category = self._get_query_and_category()
        return self._serializer_class_for(category)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        _, category = self._get_query_and_category()
        context.update(self._context_for(self.request, category))
        return context

    def get_queryset(self):
        query, category = self._get_query_and_category()
        matched_artist_ids = self._matched_artist_ids(query) if category in ('album', 'playlist', 'track') else None
        return self._build_queryset(query, category, matched_artist_ids)