from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from .models import Video
from apps.common.models import PublishStatus
from .serializers import VideoListSerializer, VideoDetailSerializer
from ..subscriptions.services import user_has_all_access


class VideoViewSet(ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['era', 'recording_year']
    search_fields = ['title', 'artists__name']
    lookup_field = 'slug'

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, slug=None):
        video = self.get_object()

        if not request.user.is_authenticated:
            return Response(
                {"detail": "برای دانلود ویدیو باید وارد حساب کاربری خود شوید."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user_has_all_access(request.user):
            return Response(
                {"detail": "برای دانلود این ویدیو نیاز به تهیه اشتراک طلایی دارید."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not video.video_file:
            return Response(
                {"detail": "فایل دانلودی برای این ویدیو در دسترس نیست."},
                status=status.HTTP_404_NOT_FOUND
            )

        download_url = request.build_absolute_uri(video.video_file.url)

        return Response(
            {"download_link": download_url},
            status=status.HTTP_200_OK
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        has_access = False
        if request and request.user.is_authenticated:
            has_access = user_has_all_access(request.user)
        context['has_all_access'] = has_access
        return context

    def get_queryset(self):
        qs = Video.objects.filter(status=PublishStatus.PUBLISHED)
        if self.action == 'retrieve':
            qs = qs.prefetch_related('artists')
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VideoDetailSerializer
        return VideoListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        return super().retrieve(request, *args, **kwargs)

