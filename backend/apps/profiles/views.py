from django.contrib.auth import update_session_auth_hash
from rest_framework import status, serializers
from rest_framework.generics import UpdateAPIView
from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import ChangePasswordSerializer, ArtistListSerializer, ArtistDetailSerializer, PlayHistorySerializer
from apps.profiles.models import UserProfile
from apps.profiles.serializers import UserProfileSerializer, UserProfileUpdateSerializer
from django.shortcuts import get_object_or_404

from django.contrib.contenttypes.models import ContentType
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.music.models import Album, Artist, Track, PlayHistory
from apps.music.serializers import ArtistSerializer, AlbumListSerializer, TrackSerializer
from apps.interactions.models import Like, Follow
from ..playlists.models import Playlist
from apps.profiles.serializers import DashboardSummarySerializer

from drf_spectacular.utils import extend_schema, inline_serializer


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserProfileSerializer})
    def get(self, request):
        profile = get_object_or_404(UserProfile.objects.select_related("user"), user=request.user)
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

    @extend_schema(request=ChangePasswordSerializer,responses={200: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()

            update_session_auth_hash(request, user)

            return Response({"detail": "Password Changed Successfilly"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ArtistViewSet(viewsets.ReadOnlyModelViewSet):

    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return ArtistListSerializer
        return ArtistDetailSerializer

    def get_queryset(self):

        if self.action == 'list':
            return Artist.objects.only('slug', 'name', 'image')

        if self.action == 'retrieve':

            tracks_queryset = Track.objects.select_related('composer', 'singer', 'album')

            albums_queryset = Album.objects.select_related('label')

            return Artist.objects.prefetch_related(
                Prefetch('albums', queryset=albums_queryset),
                Prefetch('sung_tracks', queryset=tracks_queryset),
                Prefetch('composed_tracks', queryset=tracks_queryset),
                Prefetch('related_artists', queryset=Artist.objects.only('slug', 'name', 'image'))
            )

        return Artist.objects.all()



@extend_schema(methods=['GET'], responses={200: DashboardSummarySerializer})
class UserDashboardViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]


    @extend_schema(responses={200: DashboardSummarySerializer})
    def list(self, request):
        user = request.user
        album_ct = ContentType.objects.get_for_model(Album)
        artist_ct = ContentType.objects.get_for_model(Artist)
        track_ct = ContentType.objects.get_for_model(Track)

        liked_albums_count = Like.objects.filter(user=user, content_type=album_ct).count()
        followed_artists_count = Follow.objects.filter(user=user, content_type=artist_ct).count()
        liked_songs_count = Like.objects.filter(user=user, content_type=track_ct).count()

        liked_playlists = Playlist.objects.filter(likes__user=user).count()
        followed_playlists = Playlist.objects.filter(follows__user=user).count()

        data = {
            "liked_albums_count": liked_albums_count,
            "followed_artists_count": followed_artists_count,
            "liked_songs_count": liked_songs_count,
            "saved_playlists_count": liked_playlists + followed_playlists,
        }
        return Response(data)


    @extend_schema(responses={200: AlbumListSerializer(many=True)})
    @action(detail=False, methods=['get'], url_path='liked-albums')
    def liked_albums(self, request):
        user = request.user
        album_ct = ContentType.objects.get_for_model(Album)
        liked_album_ids = Like.objects.filter(user=user, content_type=album_ct).values_list('object_id', flat=True)
        albums = Album.objects.filter(id__in=liked_album_ids)

        serializer = AlbumListSerializer(albums, many=True, context={'request': request})
        return Response(serializer.data)


    @extend_schema(responses={200: ArtistSerializer(many=True)})
    @action(detail=False, methods=['get'], url_path='followed-artists')
    def followed_artists(self, request):
        user = request.user
        artist_ct = ContentType.objects.get_for_model(Artist)
        followed_artist_ids = Follow.objects.filter(user=user, content_type=artist_ct).values_list('object_id',
                                                                                                   flat=True)
        artists = Artist.objects.filter(id__in=followed_artist_ids)

        serializer = ArtistSerializer(artists, many=True, context={'request': request})
        return Response(serializer.data)


    @extend_schema(responses={200: inline_serializer(name='SavedPlaylistsResponse',fields={'saved_playlists': serializers.ListField(child=serializers.CharField())})})
    @action(detail=False, methods=['get'], url_path='saved-playlists')
    def saved_playlists(self, request):
        user = request.user
        liked_playlists = Playlist.objects.filter(likes__user=user)
        followed_playlists = Playlist.objects.filter(follows__user=user)
        saved_playlist_titles = liked_playlists.values_list('title', flat=True)

        return Response({"saved_playlists": list(saved_playlist_titles)})


    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='history')
    def history(self, request):
        queryset = PlayHistory.objects.filter(user=request.user).select_related(
            'track__album',
            'track__composer',
            'track__singer',
            'track__instrument'
        ).order_by('-last_played_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PlayHistorySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = PlayHistorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


    @extend_schema(responses={200: TrackSerializer(many=True)})
    @action(detail=False, methods=['get'], url_path='liked-tracks')
    def liked_songs(self, request):

        user = request.user
        track_ct = ContentType.objects.get_for_model(Track)

        liked_track_ids = Like.objects.filter(
            user=user, content_type=track_ct
        ).values_list('object_id', flat=True)

        tracks = Track.objects.filter(id__in=liked_track_ids).select_related(
            'album', 'singer', 'composer'
        )
        serializer = TrackSerializer(tracks, many=True, context={'request': request})
        return Response(serializer.data)