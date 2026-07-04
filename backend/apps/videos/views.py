from rest_framework.viewsets import ReadOnlyModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .models import Video
from apps.common.models import PublishStatus
from .serializers import VideoListSerializer, VideoDetailSerializer
from ..subscriptions.services import user_has_all_access


class VideoViewSet(ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['era', 'recording_year']
    search_fields = ['title', 'artists__name']
    lookup_field = 'slug'


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
