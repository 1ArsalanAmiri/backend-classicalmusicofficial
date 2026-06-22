from django.http import HttpResponse, Http404
import mimetypes
from urllib.parse import quote
from rest_framework.permissions import AllowAny , IsAuthenticated , IsAuthenticatedOrReadOnly
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
from apps.common.filters import AlbumFilter,TrackFilter
from django.db import transaction
from rest_framework.decorators import action
from apps.common.throttles import ZipGenerationRateThrottle
from rest_framework.exceptions import PermissionDenied
from apps.common.permissions import HasStreamSubscription , user_has_download_access , user_has_stream_access , HasAllSubscription , HasDownloadSubscription
from apps.common.models import PublishStatus
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.viewsets import ReadOnlyModelViewSet
from apps.interactions.mixins import LikableMixin, FollowableMixin ,CommentableMixin
from django.db.models import F

from ..interactions.models import Comment
from ..interactions.serializers import CommentSerializer , CommentCreateSerializer

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes



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



class ArtistViewSet(FollowableMixin, LikableMixin, ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['artist_type', 'era', 'country']
    search_fields = ['name']
    lookup_field = 'slug'



class AlbumViewSet(CommentableMixin,LikableMixin,viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Album.objects.filter(status=PublishStatus.PUBLISHED).prefetch_related("tracks").annotate(annotated_total_tracks=Count("tracks"))
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AlbumFilter
    search_fields = ['title', 'composer__name', 'conductor__name']
    ordering_fields = ['release_date', 'title']
    lookup_field = 'slug'


    @extend_schema(methods=['POST'],request=CommentSerializer,responses={201: CommentSerializer},)
    @action(detail=True,methods=["get", "post"],url_path="comments",permission_classes=[IsAuthenticatedOrReadOnly],)
    def comments(self, request, slug=None):
        album = self.get_object()

        if request.method == "GET":
            comments = Comment.objects.filter(
                album=album,
                is_approved=True,
            ).select_related("user").order_by("-created_at")

            page = self.paginate_queryset(comments)

            if page is not None:
                serializer = CommentSerializer(page, many=True, context={"request": request})
                return self.get_paginated_response(serializer.data)

            serializer = CommentSerializer(comments, many=True, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = CommentCreateSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            serializer.save(user=request.user, album=album)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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



class TrackViewSet(LikableMixin, ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TrackFilter

    queryset = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related('album', 'composer', 'singer')

    serializer_class = TrackSerializer

    filterset_fields = ['instrument', 'album__slug']
    search_fields = ['title', 'composer__name', 'singer__name']
    ordering_fields = ['track_number', 'release_date']
    lookup_field = 'slug'


    @extend_schema(parameters=[
            OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='search', description='جستجو در عنوان، خواننده و آهنگساز', required=False, type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='instrument', description='فیلتر بر اساس ساز', required=False, type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),])
    @action(detail=False, methods=['get'], url_path='singles')
    @action(detail=False, methods=['get'], url_path='singles')
    def singles(self, request):

        queryset = Track.objects.filter(
            status=PublishStatus.PUBLISHED,
            album__isnull=True
        ).select_related('composer', 'singer', 'instrument')

        filtered_queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(filtered_queryset, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['get'], url_path='stream', permission_classes=[HasStreamSubscription])
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

        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response


    @action(detail=True, methods=['get'], url_path='download', permission_classes=[HasDownloadSubscription])
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


    @extend_schema(parameters=[OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),])
    @action(detail=False, methods=['get'], url_path='chosen')
    @action(detail=False, methods=['get'], url_path='chosen')
    def chosen(self, request):

        queryset = self.filter_queryset(self.get_queryset().filter(is_chosen=True))

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='record-play')
    def record_play(self, request, slug=None):
        track = self.get_object()

        Track.objects.filter(id=track.id).update(play_count=F('play_count') + 1)

        history, created = PlayHistory.objects.get_or_create(
            user=request.user,
            track=track,
            defaults={'play_count': 1, 'last_played_at': timezone.now()}
        )

        if not created:
            history.play_count = F('play_count') + 1
            history.last_played_at = timezone.now()
            history.save(update_fields=['play_count', 'last_played_at'])

        return Response({"message": "پخش با موفقیت ثبت شد."}, status=status.HTTP_200_OK)



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



class LabelViewSet(FollowableMixin,LikableMixin,viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'


    def get_queryset(self):
        queryset = Label.objects.all()
        if self.action == 'retrieve':
            queryset = queryset.annotate(
                albums_count=Count('albums', distinct=True),
                tracks_count=Count('tracks', distinct=True)
            )
        return queryset


    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LabelDetailSerializer
        return LabelListSerializer


    @extend_schema(parameters=[OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),])
    @action(detail=True, methods=['get'])
    def tracks(self, request, slug=None):
        label = self.get_object()
        tracks = label.tracks.select_related('album').all()

        page = self.paginate_queryset(tracks)
        if page is not None:
            serializer = TrackSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = TrackSerializer(tracks, many=True, context={'request': request})
        return Response(serializer.data)


    @extend_schema(parameters=[OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),])
    @action(detail=True, methods=['get'])
    def albums(self, request, slug=None):
        label = self.get_object()
        albums = label.albums.prefetch_related('tracks')

        page = self.paginate_queryset(albums)
        if page is not None:
            serializer = AlbumListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = AlbumListSerializer(albums, many=True, context={'request': request})
        return Response(serializer.data)


