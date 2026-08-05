from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Max, Count, Sum, Subquery, OuterRef, IntegerField
from django.db.models.functions import Coalesce
from django.db import transaction

from .models import Playlist, PlaylistItem
from apps.music.models import Track
from .serializers import (
    PlaylistListSerializer,
    PlaylistDetailSerializer,
    PlaylistCreateUpdateSerializer,
    TrackActionSerializer
)
from apps.interactions.mixins import LikableMixin, FollowableMixin
from apps.common.pagination import CustomMetaDataPagination
from apps.common.models import PublishStatus


def get_annotated_playlist_queryset():
    item_count_sq = (
        PlaylistItem.objects
        .filter(playlist=OuterRef('pk'))
        .order_by()
        .values('playlist')
        .annotate(c=Count('id'))
        .values('c')
    )
    duration_sq = (
        PlaylistItem.objects
        .filter(playlist=OuterRef('pk'))
        .order_by()
        .values('playlist')
        .annotate(s=Sum('track__duration_ms'))
        .values('s')
    )

    return Playlist.objects.annotate(
        annotated_total_tracks=Coalesce(
            Subquery(item_count_sq, output_field=IntegerField()), 0
        ),
        annotated_total_duration_ms=Coalesce(
            Subquery(duration_sq, output_field=IntegerField()), 0
        ),
    )


class PlaylistViewSet(LikableMixin, FollowableMixin, viewsets.ModelViewSet):
    lookup_field = "slug"
    pagination_class = CustomMetaDataPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action in ['like_toggle', 'follow_toggle']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = get_annotated_playlist_queryset().filter(is_public=True)

        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "items",
                    queryset=PlaylistItem.objects.select_related(
                        "track",
                        "track__album",
                        "track__instrument",
                        "track__genre"
                    ).prefetch_related("track__artists").order_by("order")
                )
            )
        return qs

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PlaylistCreateUpdateSerializer
        elif self.action == "retrieve":
            return PlaylistDetailSerializer
        return PlaylistListSerializer


class UserPlaylistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'title_fa', 'description']
    ordering_fields = ['created_at', 'title']
    lookup_field = 'slug'

    def get_queryset(self):
        qs = get_annotated_playlist_queryset().filter(user=self.request.user)

        if self.action == 'retrieve':
            qs = qs.prefetch_related(
                Prefetch(
                    'items',
                    queryset=PlaylistItem.objects.select_related(
                        'track', 'track__album'
                    ).prefetch_related('track__artists').order_by('order')
                )
            )
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return PlaylistListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PlaylistCreateUpdateSerializer
        elif self.action in ['add_track', 'remove_track']:
            return TrackActionSerializer
        return PlaylistDetailSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='add-track')
    def add_track(self, request, slug=None):
        playlist = self.get_object()

        if playlist.is_editorial:
            return Response(
                {"detail": "ترک‌های پلی‌لیست ادیتوریال قابل تغییر دستی نیستند."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TrackActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        track_id = serializer.validated_data['track_id']

        track = get_object_or_404(Track, id=track_id, status=PublishStatus.PUBLISHED)

        with transaction.atomic():
            max_order = PlaylistItem.objects.filter(playlist=playlist).aggregate(Max('order'))['order__max'] or 0
            item, created = PlaylistItem.objects.get_or_create(
                playlist=playlist,
                track=track,
                defaults={'order': max_order + 1}
            )

            if not created:
                return Response(
                    {"detail": "این ترک قبلاً به پلی‌لیست اضافه شده است."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {"detail": "ترک با موفقیت به پلی‌لیست اضافه شد."},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='remove-track')
    def remove_track(self, request, slug=None):
        playlist = self.get_object()

        if playlist.is_editorial:
            return Response(
                {"detail": "ترک‌های پلی‌لیست ادیتوریال قابل تغییر دستی نیستند."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TrackActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        track_id = serializer.validated_data['track_id']

        deleted_count, _ = PlaylistItem.objects.filter(
            playlist=playlist,
            track_id=track_id
        ).delete()

        if deleted_count == 0:
            return Response(
                {"detail": "این ترک در پلی‌لیست یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {"detail": "ترک با موفقیت از پلی‌لیست حذف شد."},
            status=status.HTTP_200_OK
        )