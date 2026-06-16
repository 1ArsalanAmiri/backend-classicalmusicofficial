from rest_framework import viewsets
from apps.interactions.mixins import LikableMixin, CommentableMixin, FollowableMixin
from apps.music.models import Album, Track, Artist, Label
from apps.music.serializers import AlbumListSerializer, TrackSerializer, ArtistSerializer, LabelListSerializer



class AlbumViewSet(LikableMixin, CommentableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Album.objects.all()
    serializer_class = AlbumListSerializer
    lookup_field = 'slug'


class TrackViewSet(LikableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Track.objects.all()
    serializer_class = TrackSerializer
    lookup_field = 'slug'


class ArtistViewSet(FollowableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    lookup_field = 'slug'


class LabelViewSet(FollowableMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Label.objects.all()
    serializer_class = LabelListSerializer
    lookup_field = 'slug'
