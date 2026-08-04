from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Max, Count, Sum, Subquery, OuterRef, IntegerField
from django.db.models.functions import Coalesce

from .models import Playlist, PlaylistTrack, PlaylistItem
from apps.music.models import Track
from .serializers import (
    PlaylistListSerializer,
    PlaylistDetailSerializer,
    PlaylistCreateUpdateSerializer, TrackActionSerializer
)
from django.db import transaction
from apps.interactions.mixins import LikableMixin, FollowableMixin
from apps.common.pagination import CustomMetaDataPagination
from ..common.models import PublishStatus


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
        track_count_sq = (
            PlaylistTrack.objects
            .filter(playlist=OuterRef('pk'))
            .order_by()
            .values('playlist')
            .annotate(c=Count('id'))
            .values('c')
        )
        duration_sq = (
            PlaylistTrack.objects
            .filter(playlist=OuterRef('pk'))
            .order_by()
            .values('playlist')
            .annotate(s=Sum('track__duration_ms'))
            .values('s')
        )

        queryset = Playlist.objects.annotate(
            annotated_total_tracks=Coalesce(
                Subquery(track_count_sq, output_field=IntegerField()), 0
            ),
            annotated_total_duration_ms=Coalesce(
                Subquery(duration_sq, output_field=IntegerField()), 0
            ),
        )

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "playlist_tracks",
                    queryset=PlaylistTrack.objects.select_related(
                        "track",
                        "track__album",
                        "track__instrument",
                        "track__genre"
                    ).prefetch_related("track__artists").order_by("order")
                )
            )
        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PlaylistCreateUpdateSerializer
        elif self.action == "retrieve":
            return PlaylistDetailSerializer
        return PlaylistListSerializer

    def _block_editorial_manual_track_edit(self, playlist):
        if playlist.is_editorial:
            return Response(
                {"detail": "این پلی‌لیست به‌صورت خودکار از یک آلبوم ادیتوریال ساخته شده و ترک‌های آن را نمی‌توان دستی ویرایش کرد."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @action(detail=True, methods=['post'], url_path='add-track')
    def add_track(self, request, slug=None):
        playlist = self.get_object()
        blocked = self._block_editorial_manual_track_edit(playlist)
        if blocked:
            return blocked

        track_slug = request.data.get("track_slug")
        if not track_slug:
            return Response({"detail": "track_slug is required."}, status=status.HTTP_400_BAD_REQUEST)
        track = get_object_or_404(Track, slug=track_slug)
        with transaction.atomic():
            max_order = PlaylistTrack.objects.select_for_update().filter(playlist=playlist).aggregate(Max("order"))[
                "order__max"]
            new_order = (max_order or 0) + 1
            playlist_track, created = PlaylistTrack.objects.get_or_create(
                playlist=playlist,
                track=track,
                defaults={"order": new_order},
            )
            if not created:
                return Response({"detail": "این ترک از قبل در پلی‌لیست وجود دارد."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "ترک با موفقیت اضافه شد."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='remove-track')
    def remove_track(self, request, slug=None):
        playlist = self.get_object()
        blocked = self._block_editorial_manual_track_edit(playlist)
        if blocked:
            return blocked

        track_slug = request.data.get('track_slug')
        track = get_object_or_404(Track, slug=track_slug)
        deleted_count, _ = PlaylistTrack.objects.filter(playlist=playlist, track=track).delete()
        if deleted_count == 0:
            return Response({"error": "Track not found in this playlist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserPlaylistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title']
    lookup_field = 'slug'

    def get_queryset(self):
        return Playlist.objects.filter(user=self.request.user).prefetch_related(
            Prefetch(
                'items',
                queryset=PlaylistItem.objects.select_related('track').prefetch_related(
                    'track__artists', 'track__album'
                )
            )
        )

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
        serializer = TrackActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        track_id = serializer.validated_data['track_id']
        track = get_object_or_404(Track, id=track_id, status=PublishStatus.PUBLISHED)

        item, created = PlaylistItem.objects.get_or_create(
            playlist=playlist,
            track=track
        )

        if not created:
            return Response(
                {"detail": "این ترک قبلاً به پلی‌لیست اضافه شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "ترک با موفقیت به پلی‌لیست اضافه شد."},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='remove-track')
    def remove_track(self, request, slug=None):
        playlist = self.get_object()
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
            {"message": "ترک با موفقیت از پلی‌لیست حذف شد."},
            status=status.HTTP_200_OK
        )