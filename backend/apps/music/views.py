from django.http import HttpResponse, Http404
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import *
from .tasks import process_album_archive_task , generate_album_zip_task
from rest_framework import viewsets, filters , status
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import *
from .pagination import ClassicalMusicPagination
from .filters import AlbumFilter
from rest_framework.decorators import action
from django.db import transaction
from rest_framework.decorators import action
from .throttles import ZipGenerationRateThrottle


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
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['artist_type', 'era', 'country']
    search_fields = ['name']
    lookup_field = 'slug'



class AlbumViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Album.objects.filter(status=PublishStatus.PUBLISHED).prefetch_related('tracks')
    pagination_class = ClassicalMusicPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AlbumFilter

    search_fields = ['title', 'composer__name', 'conductor__name']
    ordering_fields = ['release_date', 'title']
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return AlbumListSerializer
        return AlbumDetailSerializer

    @action(detail=True, methods=['post'], url_path='request-zip', throttle_classes=[ZipGenerationRateThrottle])
    def request_zip(self, request, slug=None):
        album = self.get_object()
        export_record, created = AlbumZipExport.objects.get_or_create(album=album)

        if not created and export_record.status == AlbumZipExport.ExportStatus.PENDING:
            return Response({
                "status": "pending",
                "message": "file is getting ready. listen to WebSocket connection"
            }, status=status.HTTP_200_OK)

        if not created and export_record.status == AlbumZipExport.ExportStatus.COMPLETED and export_record.zip_file:
            # تغییر مهم: ارجاع به اندپوینت دانلود ایمن به‌جای URL مستقیم مدیا
            download_url = request.build_absolute_uri(reverse('album-download-zip', kwargs={'slug': album.slug}))
            return Response({
                "status": "completed",
                "message": "file exists in cache",
                "download_url": download_url
            }, status=status.HTTP_200_OK)

        export_record.status = AlbumZipExport.ExportStatus.PENDING
        export_record.save()

        transaction.on_commit(lambda: generate_album_zip_task.delay(album.id, export_record.id)) # اصلاح آرگومان‌ها

        return Response({
            "status": "pending",
            "message": "request submitted successfully. please wait for zip url."
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='download-zip')
    def download_zip(self, request, slug=None):
        if not request.user.is_authenticated:
            return HttpResponse("Unauthorized", status=401)

        export = get_object_or_404(AlbumZipExport, album__slug=slug, status='COMPLETED')

        if not export.zip_file:
            raise Http404("File not found.")

        # نام فایل ذخیره‌شده در فیلد FileField
        file_path = export.zip_file.name

        response = HttpResponse()
        # ارجاع به بلاک protected_media در Nginx
        response['X-Accel-Redirect'] = f'/protected_media/{file_path}'
        response['Content-Disposition'] = f'attachment; filename="{export.album.slug}.zip"'
        return response

class TrackViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related('album', 'composer', 'singer')
    serializer_class = TrackSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = ['instrument', 'album__slug']
    search_fields = ['title', 'composer__name', 'singer__name']
    ordering_fields = ['track_number', 'release_date']
    lookup_field = 'slug'




