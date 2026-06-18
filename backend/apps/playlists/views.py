from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch , Max

from .models import Playlist, PlaylistTrack
from apps.music.models import Track
from .serializers import (
    PlaylistListSerializer,
    PlaylistDetailSerializer,
    PlaylistCreateUpdateSerializer
)
from apps.common.permissions import IsOwnerOrPublicReadOnly
from django.db import transaction
from apps.interactions.mixins import LikableMixin , FollowableMixin



class PlaylistViewSet(LikableMixin,FollowableMixin,viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrPublicReadOnly]
    lookup_field = "slug"


    def get_permissions(self):
        if self.action in ['like_toggle','follow_toggle','create']:
            return [IsAuthenticated()]
        return [IsOwnerOrPublicReadOnly()]


    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated:
            queryset = Playlist.objects.filter(
                Q(owner=user) | Q(is_public=True)
            )
        else:
            queryset = Playlist.objects.filter(is_public=True)

        queryset = queryset.select_related("owner")

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "playlist_tracks",
                    queryset=PlaylistTrack.objects.select_related(
                        "track",
                        "track__composer",
                        "track__singer",
                        "track__album",
                        "track__instrument"
                    ).order_by("order")))

        return queryset


    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PlaylistCreateUpdateSerializer
        elif self.action == "retrieve":
            return PlaylistDetailSerializer
        return PlaylistListSerializer


    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if not queryset.exists():
            return Response(
                {
                    "results": [],
                    "message": "No playlists yet"
                },
                status=status.HTTP_200_OK
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "results": serializer.data,
                "message": "Playlists retrieved successfully."
            },
            status=status.HTTP_200_OK
        )


    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


    @action(detail=True, methods=['post'], url_path='add-track')
    def add_track(self, request, slug=None):
        playlist = self.get_object()

        track_slug = request.data.get("track_slug")
        if not track_slug:
            return Response({"detail": "track_slug is required."},status=status.HTTP_400_BAD_REQUEST)

        track = get_object_or_404(Track, slug=track_slug)

        with transaction.atomic():
            max_order = PlaylistTrack.objects.select_for_update().filter(playlist=playlist).aggregate(Max("order"))["order__max"]

            new_order = (max_order or 0) + 1

            playlist_track, created = PlaylistTrack.objects.get_or_create(playlist=playlist,track=track,defaults={"order": new_order},)

            if not created:
                return Response({"detail": "این ترک از قبل در پلی‌لیست وجود دارد."},status=status.HTTP_400_BAD_REQUEST,)
        return Response({"detail": "ترک با موفقیت اضافه شد."},status=status.HTTP_201_CREATED,)


    @action(detail=True, methods=['post'], url_path='remove-track')
    def remove_track(self, request, slug=None):
        playlist = self.get_object()
        if playlist.owner != request.user:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        track_slug = request.data.get('track_slug')
        track = get_object_or_404(Track, slug=track_slug)

        deleted_count, _ = PlaylistTrack.objects.filter(
            playlist=playlist,
            track=track
        ).delete()

        if deleted_count == 0:
            return Response({"error": "Track not found in this playlist."}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


