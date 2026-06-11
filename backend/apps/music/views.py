from django.http import HttpResponse, Http404
import mimetypes
from urllib.parse import quote
from django.urls import reverse
from rest_framework.permissions import AllowAny , IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import *
from .tasks import process_album_archive_task , generate_album_zip_task
from rest_framework import viewsets, filters , status
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import *
from apps.common.pagination import ClassicalMusicPagination
from apps.common.filters import AlbumFilter
from django.db import transaction
from rest_framework.decorators import action
from apps.common.throttles import ZipGenerationRateThrottle
from rest_framework.exceptions import PermissionDenied

from apps.subscriptions.services import (SubscriptionHistory, get_active_subscription ,
        user_has_download_access, user_has_stream_access ,
        user_has_video_stream_access ,Q)

from apps.common.permissions import HasStreamSubscription , user_has_download_access , user_has_stream_access , HasAllSubscription , HasDownloadSubscription
from apps.common.models import PublishStatus
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page



class AlbumBatchUploadAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, album_id):
        album = get_object_or_404(Album, id=album_id)
        archive_file = request.FILES.get('archive')

        if not archive_file:
            return Response({"error": "فایل ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

        ext = archive_file.name.split('.')[-1].lower()
        if ext not in ['zip', 'rar']:
            return Response({"error": "فقط فایل‌های ZIP و RAR مجاز هستند."}, status=status.HTTP_400_BAD_REQUEST)

        upload_record = AlbumArchiveUpload.objects.create(
            album=album,
            archive_file=archive_file,
            status='pending'
        )

        task = process_album_archive_task.delay(upload_record.id)

        upload_record.task_id = task.id
        upload_record.save()

        return Response({
            "message": "فایل در صف پردازش قرار گرفت.",
            "upload_id": upload_record.id,
            "task_id": task.id
        }, status=status.HTTP_202_ACCEPTED)



class ArtistViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['artist_type', 'era', 'country']
    search_fields = ['name']
    lookup_field = 'slug'



class AlbumViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Album.objects.filter(status=PublishStatus.PUBLISHED).prefetch_related('tracks')
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AlbumFilter
    search_fields = ['title', 'composer__name', 'conductor__name']
    ordering_fields = ['release_date', 'title']
    lookup_field = 'slug'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request

        if request and request.user.is_authenticated:
            context["has_stream_access"] = user_has_stream_access(request.user)
        else:
            context["has_stream_access"] = False

        return context

    def get_serializer_class(self):
        if self.action == 'list':
            return AlbumListSerializer
        return AlbumDetailSerializer

    @action(detail=True, methods=['post'], url_path='request-zip',throttle_classes=[ZipGenerationRateThrottle],permission_classes=[IsAuthenticated])
    def request_zip(self, request, slug=None):
        if not user_has_download_access(request.user):
            return Response({"error": "شما اشتراک فعال برای دانلود آلبوم را ندارید."}, status=status.HTTP_403_FORBIDDEN)

        album = self.get_object()
        export_record, created = AlbumZipExport.objects.get_or_create(album=album)

        if not created and export_record.status == AlbumZipExport.ExportStatus.PENDING:
            return Response({
                "status": "pending",
                "message": "file is getting ready. listen to WebSocket connection"
            }, status=status.HTTP_200_OK)

        if not created and export_record.status == AlbumZipExport.ExportStatus.COMPLETED and export_record.zip_file:
            download_url = request.build_absolute_uri(reverse('album-download-zip', kwargs={'slug': album.slug}))
            return Response({
                "status": "completed",
                "message": "file exists in cache",
                "download_url": download_url
            }, status=status.HTTP_200_OK)

        export_record.status = AlbumZipExport.ExportStatus.PENDING
        export_record.save()

        transaction.on_commit(lambda: generate_album_zip_task.delay(album.id, export_record.id))

        return Response({
            "status": "pending",
            "message": "request submitted successfully. please wait for zip url."
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='download-zip',permission_classes=[IsAuthenticated])
    def download_zip(self, request, slug=None):
        if not user_has_download_access(request.user):
            raise PermissionDenied("شما اشتراک فعال برای دانلود این آلبوم را ندارید.")

        export = get_object_or_404(
            AlbumZipExport,
            album__slug=slug,
            status='COMPLETED'
        )

        if not export.zip_file:
            raise Http404("File not found.")

        file_path = export.zip_file.name

        response = HttpResponse()
        response['X-Accel-Redirect'] = f'/protected_media/{file_path}'
        response['Content-Disposition'] = f'attachment; filename="{export.album.slug}.zip"'

        return response

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 30))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)



class TrackViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    queryset = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related('album', 'composer', 'singer')

    serializer_class = TrackSerializer

    filterset_fields = ['instrument', 'album__slug']
    search_fields = ['title', 'composer__name', 'singer__name']
    ordering_fields = ['track_number', 'release_date']
    lookup_field = 'slug'

    @action(detail=True, methods=['get'], url_path='stream',permission_classes=[(HasStreamSubscription | HasAllSubscription)])
    def stream(self, request, slug=None):
        track = self.get_object()

        if not track.audio_file:
            raise Http404("Audio not found")

        audio_path = track.audio_file.name

        content_type, _ = mimetypes.guess_type(audio_path)
        content_type = content_type or 'audio/mpeg'

        response = HttpResponse()

        response['X-Accel-Redirect'] = f"/protected_media/{audio_path}"
        response['Content-Type'] = content_type
        response['Content-Disposition'] = 'inline'
        response['Accept-Ranges'] = 'bytes'
        return response


    @action(detail=True, methods=['get'], url_path='download',permission_classes=[(HasDownloadSubscription | HasAllSubscription)])
    def download(self , request, slug=None):
        track = self.get_object()

        if not track.audio_file:
            raise Http404("Audio file not found")

        audio_path = track.audio_file.name

        content_type, _ = mimetypes.guess_type(audio_path)
        content_type = content_type or 'audio/mpeg'

        filename = audio_path.split('/')[-1]
        encoded_filename = quote(filename)

        response = HttpResponse()
        response['X-Accel-Redirect'] = f"/protected_media/{audio_path}"
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response['Content-Type'] = content_type
        return response



class GenreViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = GenreSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Genre.objects.annotate(
            track_count=Count('tracks')
        ).order_by('-track_count', 'name')

    @method_decorator(cache_page(60 * 60 * 24))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 60 * 24))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)



class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InstrumentSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Instrument.objects.annotate(
            track_count=Count('tracks')
        ).order_by('-track_count', 'name')

    @method_decorator(cache_page(60 * 60 * 24))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 60 * 24))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)



class EraListView(APIView):

    @method_decorator(cache_page(60 * 60 * 24 * 7))
    def get(self, request):
        eras = [
            {
                "id": key,
                "name": label
            }
            for key, label in EraChoices.choices
        ]
        return Response(eras)
