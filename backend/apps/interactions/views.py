from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Exists, Value, BooleanField
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.interactions.mixins import LikableMixin, FollowableMixin, CommentableMixin
from apps.interactions.models import Like, Follow
from apps.music.models import Album, Track, Artist, Label
from apps.music.serializers import AlbumListSerializer, TrackSerializer, ArtistSerializer, LabelListSerializer


class AlbumViewSet(LikableMixin, CommentableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Album.objects.all()
    serializer_class = AlbumListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)

        if user and user.is_authenticated:
            album_ct = ContentType.objects.get_for_model(Album)
            liked_subquery = Like.objects.filter(
                user=user,
                content_type=album_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(liked_subquery))
        else:
            qs = qs.annotate(is_liked=Value(False, output_field=BooleanField()))

        return qs


class TrackViewSet(LikableMixin, CommentableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Track.objects.all()
    serializer_class = TrackSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)

        if user and user.is_authenticated:
            track_ct = ContentType.objects.get_for_model(Track)
            liked_subquery = Like.objects.filter(
                user=user,
                content_type=track_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(liked_subquery))
        else:
            qs = qs.annotate(is_liked=Value(False, output_field=BooleanField()))

        return qs


class ArtistViewSet(FollowableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)

        if user and user.is_authenticated:
            artist_ct = ContentType.objects.get_for_model(Artist)
            followed_subquery = Follow.objects.filter(
                user=user,
                content_type=artist_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_followed=Exists(followed_subquery))
        else:
            qs = qs.annotate(is_followed=Value(False, output_field=BooleanField()))

        return qs


class LabelViewSet(FollowableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Label.objects.all()
    serializer_class = LabelListSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)

        if user and user.is_authenticated:
            label_ct = ContentType.objects.get_for_model(Label)
            followed_subquery = Follow.objects.filter(
                user=user,
                content_type=label_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_followed=Exists(followed_subquery))
        else:
            qs = qs.annotate(is_followed=Value(False, output_field=BooleanField()))

        return qs