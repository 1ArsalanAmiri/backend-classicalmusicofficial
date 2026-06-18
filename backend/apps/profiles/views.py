from django.contrib.auth import update_session_auth_hash
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import UpdateAPIView

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from .serializers import ChangePasswordSerializer
from apps.profiles.models import UserProfile, ArtistProfile
from apps.profiles.serializers import UserProfileSerializer, UserProfileUpdateSerializer ,ArtistProfileSerializer
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ReadOnlyModelViewSet


from django.contrib.contenttypes.models import ContentType
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.music.models import Album,Artist
from apps.music.serializers import ArtistSerializer , AlbumListSerializer
from apps.interactions.models import Like, Comment, Follow
from ..playlists.models import Playlist
from ..playlists.serializers import PlaylistListSerializer


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_object_or_404(
            UserProfile.objects.select_related("user"),
            user=request.user
        )

        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)



class UpdateProfileView(UpdateAPIView):
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_object(self):
        return get_object_or_404(UserProfile, user=self.request.user)



class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()

            update_session_auth_hash(request, user)

            return Response({"detail": "Password Changed Successfilly"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ArtistProfileViewSet(ReadOnlyModelViewSet):
    serializer_class = ArtistProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    lookup_url_kwarg = "slug"

    queryset = ArtistProfile.objects.select_related("artist").prefetch_related("artist__albums","artist__tracks","artist__related_artists")

    def get_object(self):
        slug = self.kwargs.get(self.lookup_url_kwarg)
        return get_object_or_404(self.queryset,artist__slug=slug)




class UserDashboardViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='liked-albums')
    def liked_albums(self, request):
        user = request.user
        album_ct = ContentType.objects.get_for_model(Album)
        liked_album_ids = Like.objects.filter(user=user, content_type=album_ct).values_list('object_id', flat=True)
        albums = Album.objects.filter(id__in=liked_album_ids)

        serializer = AlbumListSerializer(albums, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='followed-artists')
    def followed_artists(self, request):
        user = request.user
        artist_ct = ContentType.objects.get_for_model(Artist)
        followed_artist_ids = Follow.objects.filter(user=user, content_type=artist_ct).values_list('object_id',
                                                                                                   flat=True)
        artists = Artist.objects.filter(id__in=followed_artist_ids)

        serializer = ArtistSerializer(artists, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='saved-playlists')
    def saved_playlists(self, request):
        user = request.user
        liked_playlists = Playlist.objects.filter(likes__user=user)
        followed_playlists = Playlist.objects.filter(follows__user=user)
        saved_playlist_titles = liked_playlists.values_list('title', flat=True)

        return Response({"saved_playlists": list(saved_playlist_titles)})
