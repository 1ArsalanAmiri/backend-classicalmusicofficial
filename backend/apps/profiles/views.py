from django.contrib.auth import update_session_auth_hash
from rest_framework import status, generics
from rest_framework.generics import UpdateAPIView, RetrieveAPIView
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import ChangePasswordSerializer
from apps.profiles.models import UserProfile, ArtistProfile
from apps.profiles.serializers import UserProfileSerializer, UserProfileUpdateSerializer ,ArtistProfileSerializer
from django.shortcuts import get_object_or_404
from apps.music.models import Artist
from rest_framework.viewsets import ReadOnlyModelViewSet, ViewSet, GenericViewSet
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page


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

    queryset = ArtistProfile.objects.select_related("artist")

    def get_object(self):
        slug = self.kwargs.get(self.lookup_url_kwarg)

        return get_object_or_404(
            self.queryset,
            artist__slug=slug
        )
