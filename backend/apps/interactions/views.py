from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Exists
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.interactions.mixins import LikableMixin, FollowableMixin, CommentableMixin
from apps.music.models import Album, Track, Artist, Label
from apps.music.serializers import AlbumListSerializer, TrackSerializer, ArtistSerializer, LabelListSerializer
from .models import Like ,Comment
from .serializers import CommentSerializer



class AlbumViewSet(CommentableMixin,viewsets.ReadOnlyModelViewSet):
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
            qs = qs.annotate(is_liked_by_user=Exists(liked_subquery))
        return qs


    @action(detail=True, methods=['get', 'post'], url_path='comment')
    def comments(self, request, slug=None):
        album = self.get_object()

        if request.method == 'GET':
            comments = Comment.objects.filter(album=album, is_approved=True)
            serializer = CommentSerializer(comments, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            if not request.user.is_authenticated:
                return Response({"detail": "لطفا ابتدا ثبت نام/لاگین کنید."}, status=401)

            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(user=request.user, album=album)
            return Response(
                {"message": "کامنت شما ثبت شد و پس از تایید نمایش داده خواهد شد.", "data": serializer.data},
                status=201
            )


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

