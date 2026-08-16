from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Exists
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.interactions.mixins import LikableMixin, FollowableMixin, CommentableMixin
from apps.music.models import Album, Track, Artist, Label
from apps.music.serializers import AlbumListSerializer, TrackSerializer, ArtistSerializer, LabelListSerializer
from apps.interactions.models import Like


class AlbumViewSet(LikableMixin, CommentableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Album.objects.all()
    serializer_class = AlbumListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            album_ct = ContentType.objects.get_for_model(Album)
            liked_subquery = Like.objects.filter(
                user=user,
                content_type=album_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(liked_subquery))
        return qs


class TrackViewSet(LikableMixin, CommentableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Track.objects.all()
    serializer_class = TrackSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            track_ct = ContentType.objects.get_for_model(Track)
            liked_subquery = Like.objects.filter(
                user=user,
                content_type=track_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(liked_subquery))
        return qs


class ArtistViewSet(FollowableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    lookup_field = 'slug'


class LabelViewSet(FollowableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Label.objects.all()
    serializer_class = LabelListSerializer
    lookup_field = 'slug'