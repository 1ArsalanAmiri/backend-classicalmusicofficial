from django.http import HttpResponse, Http404, FileResponse
import mimetypes
from urllib.parse import quote
from rest_framework.permissions import AllowAny , IsAuthenticated , IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import *
from .tasks import process_album_archive_task
from rest_framework import viewsets, filters , status
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import *
from apps.common.pagination import ClassicalMusicPagination
from apps.common.filters import AlbumFilter,TrackFilter
from django.db import transaction
from rest_framework.decorators import action
from apps.common.permissions import user_has_stream_access ,user_has_download_access , user_has_all_access
from apps.common.models import PublishStatus
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.viewsets import ReadOnlyModelViewSet
from apps.interactions.mixins import LikableMixin, FollowableMixin ,CommentableMixin
from django.db.models import F
from django.views.decorators.vary import vary_on_headers
from ..common.utils.clean_file_name import get_clean_download_filename
from ..interactions.models import Comment
from ..interactions.serializers import CommentSerializer , CommentCreateSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from asgiref.sync import sync_to_async
from rest_framework.decorators import api_view, permission_classes
from django.conf import settings
import os
import tempfile
import zipfile
from django.core.files import File
from django.utils import timezone
from .models import Album, AlbumArchiveUpload, Track, Artist ,Genre
from django.db.models import Count, Prefetch, Sum, Value
from django.db.models.functions import Coalesce


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



class AlbumViewSet(CommentableMixin, LikableMixin, viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Album.objects.filter(status=PublishStatus.PUBLISHED).prefetch_related("tracks").annotate(annotated_total_tracks=Count("tracks"))
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AlbumFilter
    search_fields = ['title', 'main_artists__name', 'credits__artist__name']
    ordering_fields = ['release_year', 'title']
    lookup_field = 'slug'

    def get_on_this_album(self, obj):
        main_artists_ids = [artist.id for artist in obj.main_artists.all()]
        track_artists_ids = [
            artist.id
            for track in obj.tracks.all()for artist in track.artists.all()
        ]
        all_artist_ids = set(main_artists_ids) | set(track_artists_ids)
        all_artist_ids.discard(None)
        if not all_artist_ids:
            return []
        artists = Artist.objects.filter(id__in=all_artist_ids).distinct()
        serializer = ArtistBasicSerializer(artists, many=True, context=self.context)
        return serializer.data

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
            context["has_download_access"] = user_has_download_access(request.user)
        else:
            context["has_stream_access"] = False
            context["has_download_access"] = False
        return context

    def get_serializer_class(self):
        if self.action == 'list':
            return AlbumListSerializer
        return AlbumDetailSerializer

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 30))
    @method_decorator(vary_on_headers('Authorization', 'Cookie'))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)



class TrackViewSet(LikableMixin, ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TrackFilter
    queryset = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related('album').prefetch_related('artists')
    serializer_class = TrackSerializer
    filterset_fields = ['instrument', 'album__slug']
    search_fields = ['title', 'artists__name']
    ordering_fields = ['track_number', 'release_date']
    lookup_field = 'slug'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        if request and request.user.is_authenticated:
            context["has_stream_access"] = user_has_stream_access(request.user)
            context["has_download_access"] = user_has_download_access(request.user)
        else:
            context["has_stream_access"] = False
            context["has_download_access"] = False
        return context


    @extend_schema(parameters=[
        OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='search', description='جستجو در عنوان، خواننده و آهنگساز', required=False, type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='instrument', description='فیلتر بر اساس ساز', required=False, type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
    ])
    @action(detail=False, methods=['get'], url_path='singles')
    def singles(self, request):
        queryset = Track.objects.filter(
            status=PublishStatus.PUBLISHED,
            album__isnull=True
        ).select_related('instrument').prefetch_related('artists')

        filtered_queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(filtered_queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='stream')
    def stream(self, request, slug=None):
        track = self.get_object()
        if not track.audio_file:
            return Response({"detail": "فایل صوتی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        if not user_has_stream_access(request.user):
            return Response({"detail": "شما اشتراک فعال برای پخش این آهنگ را ندارید."},status=status.HTTP_403_FORBIDDEN)
        file_path = track.audio_file.name
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'audio/mpeg'
        file_url = track.audio_file.url
        accel_path = file_url.replace(settings.MEDIA_URL, '/protected-media/')
        response = HttpResponse()
        response['X-Accel-Redirect'] = accel_path
        response['Content-Type'] = content_type
        from urllib.parse import quote
        safe_filename = quote(file_path.split("/")[-1])
        response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
        return response

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='download')
    def download(self, request, slug=None):
        track = self.get_object()
        if not track.audio_file:
            return Response({"detail": "فایل صوتی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        if not user_has_download_access(request.user):
            return Response({"detail": "شما اشتراک فعال برای دانلود این آهنگ را ندارید."}, status=status.HTTP_403_FORBIDDEN)
        file_path = track.audio_file.name
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'audio/mpeg'
        file_url = track.audio_file.url
        accel_path = file_url.replace(settings.MEDIA_URL, '/protected-media/')
        response = HttpResponse()
        response['X-Accel-Redirect'] = accel_path
        response['Content-Type'] = content_type
        from urllib.parse import quote
        safe_filename = quote(file_path.split("/")[-1])
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        return response

    @extend_schema(parameters=[OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),])
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
        history, created = PlayHistory.objects.update_or_create(user=request.user,track=track,defaults={'last_played_at': timezone.now()})
        if not created:
            PlayHistory.objects.filter(id=history.id).update(play_count=F('play_count') + 1)
        else:
            PlayHistory.objects.filter(id=history.id).update(play_count=1)
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



class LabelViewSet(FollowableMixin, LikableMixin, viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = Label.objects.all()
        if self.action == 'retrieve':
            queryset = queryset.annotate(
                albums_count=Count('albums_by_label', distinct=True),
                tracks_count=Count('tracks', distinct=True)
            ).prefetch_related(
                Prefetch(
                    'albums_by_label',
                    queryset=Album.objects.filter(status=PublishStatus.PUBLISHED).annotate(
                        annotated_total_tracks=Count('tracks')
                    )
                ),
                Prefetch(
                    'tracks',
                    queryset=Track.objects.filter(
                        status=PublishStatus.PUBLISHED,
                        album__isnull=True
                    ).select_related('album', 'instrument').prefetch_related('artists'),
                    to_attr='prefetched_singles'
                )
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LabelDetailSerializer
        return LabelListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        if request and request.user.is_authenticated:
            context["has_stream_access"] = user_has_stream_access(request.user)
            context["has_download_access"] = user_has_download_access(request.user)
        else:
            context["has_stream_access"] = False
            context["has_download_access"] = False
        return context

    @extend_schema(parameters=[OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),])
    @action(detail=True, methods=['get'])
    def tracks(self, request, slug=None):
        label = self.get_object()
        tracks = label.tracks.select_related('album').all()
        page = self.paginate_queryset(tracks)
        if page is not None:
            serializer = TrackSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = TrackSerializer(tracks, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(parameters=[OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),])
    @action(detail=True, methods=['get'])
    def albums(self, request, slug=None):
        label = self.get_object()
        albums = label.albums_by_label.prefetch_related('tracks').annotate(annotated_total_tracks=Count('tracks'))
        page = self.paginate_queryset(albums)
        if page is not None:
            serializer = AlbumListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = AlbumListSerializer(albums, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


@sync_to_async
def get_album_and_tracks(album_slug):
    album = get_object_or_404(Album, slug=album_slug)
    tracks = list(album.tracks.select_related())
    return album, tracks


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_album_zip_api(request, album_slug):
    if not user_has_download_access(request.user):
        return Response(
            {"detail": "شما اشتراک فعال برای دانلود آلبوم را ندارید."},
            status=status.HTTP_403_FORBIDDEN
        )
    album = get_object_or_404(Album, slug=album_slug)
    tracks = list(album.tracks.all())

    if not tracks:
        return Response({"error": "آهنگی توی این آلبوم پیدا نشد. دوباره برسی کنید یا به پشتیبانی پیام بدید."}, status=status.HTTP_404_NOT_FOUND)

    with transaction.atomic():
        existing_export = AlbumZipExport.objects.select_for_update().filter(
            album=album,
            status='completed',
            zip_file__isnull=False
        ).exclude(zip_file='').first()

    file_exists_physically = False
    if existing_export and existing_export.zip_file:
        if os.path.exists(existing_export.zip_file.path):
            file_exists_physically = True

    if file_exists_physically:
        export_record = existing_export
    else:
        export_record = AlbumZipExport(album=album, status='pending')
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')

        try:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for track in tracks:
                    audio = getattr(track, "audio_file", None)
                    if audio and audio.name and os.path.exists(audio.path):
                        file_path = audio.path
                        file_name = os.path.basename(file_path)
                        zipf.write(file_path, arcname=file_name)

            with open(temp_zip.name, 'rb') as f:
                export_record.zip_file.save(f"{album.slug}.zip", File(f), save=False)

            export_record.status = 'completed'
            export_record.save()

        except Exception as e:
            os.unlink(temp_zip.name)
            return Response({"error": "ساخت فایل زیپ به مشکل خورد ، به پشتیبانی پیام بدید."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if os.path.exists(temp_zip.name):
                os.unlink(temp_zip.name)

    file_url = export_record.zip_file.url
    nginx_internal_path = file_url.replace(settings.MEDIA_URL, '/protected-media/')

    response = HttpResponse()
    response['X-Accel-Redirect'] = nginx_internal_path
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(export_record.zip_file.name)}"'
    response['Content-Type'] = 'application/zip'

    return response