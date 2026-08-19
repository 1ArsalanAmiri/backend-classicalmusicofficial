from django.http import HttpResponse
import mimetypes
import logging
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import *
from .tasks import process_album_archive_task
from rest_framework import viewsets, filters, status
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import *
from apps.common.pagination import ClassicalMusicPagination
from apps.common.filters import AlbumFilter, TrackFilter
from django.db import transaction
from rest_framework.decorators import action
from apps.common.permissions import user_has_stream_access, user_has_all_access
from apps.common.models import PublishStatus
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.viewsets import ReadOnlyModelViewSet
from apps.interactions.mixins import LikableMixin, FollowableMixin, CommentableMixin
from django.db.models import F, Count, Sum, Prefetch, OuterRef, Exists
from django.db.models.functions import Coalesce
from django.views.decorators.vary import vary_on_headers
from ..interactions.models import Comment, Like, Follow
from ..interactions.serializers import CommentSerializer, CommentCreateSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from asgiref.sync import sync_to_async
from rest_framework.decorators import api_view, permission_classes
import os
import tempfile
import zipfile
from django.core.files import File
from django.utils import timezone
from urllib.parse import quote
from django.core.files.storage import default_storage
from django.contrib.contenttypes.models import ContentType
from .tasks import generate_album_zip_task
from celery.result import AsyncResult
from celery.exceptions import TimeoutError as CeleryTimeoutError
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import FileResponse
from django.views.decorators.cache import never_cache
from rest_framework import generics
from apps.common.pagination import ClassicalMusicPagination, LandingPagination


logger = logging.getLogger(__name__)


class AlbumBatchUploadAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated]

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

@method_decorator(never_cache, name='dispatch')
class ArtistViewSet(FollowableMixin, LikableMixin, ReadOnlyModelViewSet):
    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['artist_type', 'era', 'country']
    search_fields = ['name', 'nickname']
    lookup_field = 'slug'

    def get_queryset(self):
        qs = Artist.objects.all()
        user = self.request.user
        if user.is_authenticated:
            artist_ct = ContentType.objects.get_for_model(Artist)
            followed_subquery = Follow.objects.filter(
                user=user,
                content_type=artist_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_followed=Exists(followed_subquery))
        return qs

    def get_permissions(self):
        # مسیرهای عمومی (لیست آلبوم‌ها و جزئیات)
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        # در بخش کامنت، فقط دیدن کامنت‌ها آزاده اما ارسالش توکن می‌خواد
        elif self.action == 'comments':
            if self.request.method == 'POST':
                return [IsAuthenticated()]
            return [AllowAny()]
        # لایک و آن‌لایک کردن
        elif self.action in ['like', 'unlike']:
            return [IsAuthenticated()]
        # عملیات‌های write مثل ساخت، آپدیت و حذف آلبوم
        return [IsAuthenticated()]

@method_decorator(never_cache, name='dispatch')
class AlbumViewSet(CommentableMixin, LikableMixin, viewsets.ModelViewSet):
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AlbumFilter
    search_fields = ['title', 'main_artists__name', 'main_artists__nickname', 'credits__artist__name','credits__artist__nickname']
    ordering_fields = ['release_year', 'title']
    lookup_field = 'slug'
    album_type = AlbumType.OFFICIAL

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        # در بخش کامنت، فقط دیدن کامنت‌ها آزاده اما ارسالش توکن می‌خواد
        # نکته: اکشن کامنت از CommentableMixin میاد و اسمش manage_comments هست، نه comments
        elif self.action == 'manage_comments':
            if self.request.method == 'POST':
                return [IsAuthenticated()]
            return [AllowAny()]
        # لایک کردن / برداشتن لایک - اکشن واقعی از LikableMixin با اسم like_toggle میاد
        elif self.action == 'like_toggle':
            return [IsAuthenticated()]
        # عملیات‌های write مثل ساخت، آپدیت و حذف آلبوم
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Album.objects.filter(status=PublishStatus.PUBLISHED).select_related('label').prefetch_related(
            'main_artists',
            Prefetch(
                'tracks',
                queryset=Track.objects.filter(status=PublishStatus.PUBLISHED).prefetch_related('artists')
            )
        ).annotate(
            annotated_total_tracks=Count("tracks", distinct=True),
            annotated_total_duration_ms=Coalesce(Sum("tracks__duration_ms"), 0)
        )

        user = self.request.user
        if user.is_authenticated:
            album_ct = ContentType.objects.get_for_model(Album)
            liked_subquery = Like.objects.filter(
                user=user,
                content_type=album_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(liked_subquery))

        # 🟢 تغییر هوشمندانه: اگر در اکشن download_zip هستیم، فیلتر نوع آلبوم
        # برداشته می‌شود تا پلی‌لیست‌های ادیتوریال هم توسط اسلاگ پیدا شوند.
        if getattr(self, 'action', None) != 'download_zip':
            qs = qs.filter(album_type=self.album_type)

        return qs

    # نکته: اکشن‌های «comments» و «like» که قبلاً اینجا با پیاده‌سازی دستی
    # (و باگ‌دار) تعریف شده بودن حذف شدن. AlbumViewSet از CommentableMixin و
    # LikableMixin ارث‌بری می‌کنه که خودشون همین مسیرها (comments/ و like/)
    # رو با روش صحیح (بر اساس content_type + object_id) پیاده‌سازی می‌کنن.
    # نسخه‌ی قبلی مستقیم روی Comment.objects.filter(album=...) و album.likes
    # کوئری می‌زد که چون این فیلد/رابطه‌ها اصلاً روی مدل وجود ندارن باعث
    # AttributeError/FieldError و ارور 500 می‌شد (و چون هر دو روی همون
    # url_path ثبت می‌شدن، عملاً نسخه‌ی درستِ ارث‌بری‌شده رو هم شادو می‌کردن).

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        if request and request.user.is_authenticated:
            context["has_stream_access"] = user_has_stream_access(request.user)
            context["has_download_access"] = user_has_all_access(request.user)
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

    # حداکثر مدتی که این اندپوینت حاضره توی همون درخواست اول منتظر بمونه
    # تا فایل زیپ آماده بشه. اگه بیشتر از این طول کشید (آلبوم خیلی بزرگ،
    # یا سرور شلوغ)، به‌جای قفل نگه‌داشتن کانکشن، برمی‌گرده به همون رفتار
    # قبلی (PENDING/PROCESSING) تا فرانت با poll دوباره چک کنه.
    # نکته: این عدد باید کوچیک‌تر از proxy_read_timeout توی Nginx و
    # timeout توی gunicorn باشه، وگرنه قبل از این‌که Django جواب بده،
    # Nginx خودش 504 برمی‌گردونه. (مثلاً روی این‌ها 40-45 ثانیه بذار.)
    ZIP_WAIT_TIMEOUT = 30  # ثانیه

    def _serve_zip_file(self, album, zip_export):
        response = HttpResponse()
        response['X-Accel-Redirect'] = f"/protected-media/{zip_export.zip_file.name}"
        response['Content-Type'] = 'application/zip'
        safe_filename = quote(f"{album.slug}.zip")
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        return response

    @action(detail=True, methods=['get'], url_path='download-zip', permission_classes=[IsAuthenticated])
    def download_zip(self, request, slug=None):
        album = self.get_object()

        # بررسی اشتراک و دسترسی کاربر
        if not user_has_all_access(request.user):
            return Response(
                {"detail": "شما اشتراک فعال برای دانلود این آلبوم را ندارید."},
                status=status.HTTP_403_FORBIDDEN
            )

        zip_export = album.zip_exports.order_by('created_at').last()

        # وضعیت ۱: فایل از قبل کاملاً آماده است -> فوری سرو کن
        if zip_export and zip_export.status == AlbumZipExport.StatusChoices.COMPLETED and zip_export.zip_file:
            return self._serve_zip_file(album, zip_export)

        # وضعیت ۲: یک تسک دیگه از قبل در حال ساخت همین زیپه -> به همون وصل شو
        # (به‌جای صف کردن یک تسک تکراری برای درخواست‌های همزمان چند کاربر)
        if zip_export and zip_export.status == AlbumZipExport.StatusChoices.PROCESSING and zip_export.task_id:
            async_result = AsyncResult(zip_export.task_id)
        else:
            async_result = generate_album_zip_task.delay(album.id)

        # وضعیت ۳: منتظر می‌مونیم (بلاک می‌کنیم) تا حداکثر ZIP_WAIT_TIMEOUT
        # ثانیه که تسک تموم بشه، و در همون درخواست اول جواب رو برمی‌گردونیم.
        try:
            async_result.get(timeout=self.ZIP_WAIT_TIMEOUT, propagate=True)
        except CeleryTimeoutError:
            return Response(
                {
                    "detail": "ساخت فایل ZIP بیشتر از حد معمول طول کشید. لطفاً چند لحظه دیگر مجدداً تلاش کنید.",
                    "status": "PROCESSING",
                },
                status=status.HTTP_202_ACCEPTED
            )
        except Exception:
            logger.exception("generate_album_zip_task failed for album_id=%s", album.id)
            return Response(
                {"detail": "در ساخت فایل ZIP خطایی رخ داد. لطفاً دوباره تلاش کنید.", "status": "FAILED"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # تسک تموم شد؛ رکورد رو دوباره از دیتابیس بخون و فایل رو سرو کن
        zip_export = album.zip_exports.order_by('created_at').last()
        if zip_export and zip_export.status == AlbumZipExport.StatusChoices.COMPLETED and zip_export.zip_file:
            return self._serve_zip_file(album, zip_export)

        return Response(
            {"detail": "فایل آماده نشد، لطفاً دوباره تلاش کنید.", "status": "PROCESSING"},
            status=status.HTTP_202_ACCEPTED
        )

@method_decorator(never_cache, name='dispatch')
class TrackViewSet(LikableMixin, ReadOnlyModelViewSet):
    pagination_class = ClassicalMusicPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TrackFilter
    queryset = Track.objects.filter(status=PublishStatus.PUBLISHED).select_related('album').prefetch_related('artists',
                                                                                                             Prefetch(
                                                                                                                 'album__main_artists',
                                                                                                                 queryset=Artist.objects.all()))
    serializer_class = TrackSerializer
    filterset_fields = ['instrument', 'album__slug']
    search_fields = ['title', 'artists__name', 'artists__nickname']
    ordering_fields = ['track_number', 'release_date']
    lookup_field = 'slug'

    def get_permissions(self):
        # ۱. اندپوینت‌های کاملاً عمومی که نیاز به توکن ندارند
        if self.action in ['list', 'retrieve', 'singles', 'chosen']:
            return [AllowAny()]

        # ۲. اکشن‌هایی که حتماً نیاز به توکن (احراز هویت) دارند (شامل استریم و دانلود)
        if self.action in ['stream', 'download', 'record_play', 'like_toggle']:
            return [IsAuthenticated()]

        # پیش‌فرض برای هر اکشن دیگری
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            track_ct = ContentType.objects.get_for_model(Track)
            liked_subquery = Like.objects.filter(
                user=user,
                content_type=track_ct,
                object_id=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(liked_subquery))
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        if request and request.user.is_authenticated:
            context["has_stream_access"] = user_has_stream_access(request.user)
            context["has_download_access"] = user_has_all_access(request.user)
        else:
            context["has_stream_access"] = False
            context["has_download_access"] = False
        return context

    @extend_schema(parameters=[
        OpenApiParameter(name='page', description='شماره صفحه', required=False, type=OpenApiTypes.INT,
                         location=OpenApiParameter.QUERY),
        OpenApiParameter(name='search', description='جستجو در عنوان، خواننده و آهنگساز', required=False,
                         type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='instrument', description='فیلتر بر اساس ساز', required=False, type=OpenApiTypes.STR,
                         location=OpenApiParameter.QUERY),
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
            return Response({"detail": "شما اشتراک فعال برای پخش این آهنگ را ندارید."},
                            status=status.HTTP_403_FORBIDDEN)
        safe_filename = os.path.basename(track.audio_file.name)
        content_type, _ = mimetypes.guess_type(track.audio_file.name)
        response = HttpResponse()
        response['X-Accel-Redirect'] = f"/protected-media/{track.audio_file.name}"
        response['Content-Type'] = content_type or 'audio/mpeg'
        response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
        return response

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='download')
    def download(self, request, slug=None):
        track = self.get_object()
        if not track.audio_file:
            return Response({"detail": "فایل صوتی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        if not user_has_all_access(request.user):
            return Response({"detail": "شما اشتراک فعال برای دانلود این آهنگ را ندارید."},
                            status=status.HTTP_403_FORBIDDEN)

        content_type, _ = mimetypes.guess_type(track.audio_file.name)
        accel_path = f"/protected-media/{track.audio_file.name}"

        response = HttpResponse()
        response['X-Accel-Redirect'] = accel_path
        response['Content-Type'] = content_type or 'application/octet-stream'
        safe_filename = quote(track.audio_file.name.split("/")[-1])
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        return response

    @extend_schema(parameters=[
        OpenApiParameter(name="page", description="شماره صفحه", required=False, type=OpenApiTypes.INT,
                         location=OpenApiParameter.QUERY),
        OpenApiParameter(name="page_size", description="تعداد آیتم در هر صفحه", required=False, type=OpenApiTypes.INT,
                         location=OpenApiParameter.QUERY),
        OpenApiParameter(name="search", description="جستجو در عنوان، نام و لقب هنرمند", required=False,
                         type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
    ])
    @action(detail=False, methods=["get"], url_path="chosen")
    def chosen(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(is_chosen=True)
        )

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
            defaults={'last_played_at': timezone.now(), 'play_count': 1}
        )
        if not created:
            PlayHistory.objects.filter(id=history.id).update(
                play_count=F('play_count') + 1,
                last_played_at=timezone.now()
            )
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

@method_decorator(never_cache, name='dispatch')
class LabelViewSet(FollowableMixin, LikableMixin, viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Label.objects.all()

        user = self.request.user
        if user.is_authenticated:
            label_ct = ContentType.objects.get_for_model(Label)
            followed_subquery = Follow.objects.filter(
                user=user,
                content_type=label_ct,
                object_id=OuterRef('pk')
            )
            queryset = queryset.annotate(is_followed=Exists(followed_subquery))

        if self.action == 'retrieve':
            queryset = queryset.annotate(
                albums_count=Count('albums_by_label', distinct=True),
                tracks_count=Count('tracks', distinct=True)
            ).prefetch_related(
                Prefetch(
                    'albums_by_label',
                    queryset=Album.objects.filter(
                        status=PublishStatus.PUBLISHED,
                        album_type=AlbumType.OFFICIAL
                    ).annotate(
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
            context["has_download_access"] = user_has_all_access(request.user)
        else:
            context["has_stream_access"] = False
            context["has_download_access"] = False
        return context


class GenreDetailWithContentAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug, *args, **kwargs):
        genre = get_object_or_404(Genre, slug=slug)
        limit = int(request.query_params.get('limit', 20))

        albums = Album.objects.filter(
            tracks__genre=genre,
            status=PublishStatus.PUBLISHED,
            album_type=AlbumType.OFFICIAL
        ).distinct().annotate(
            annotated_total_tracks=Count('tracks')
        ).order_by('-release_year')[:limit]

        single_tracks = Track.objects.filter(
            genre=genre,
            album__isnull=True,
            status=PublishStatus.PUBLISHED
        ).select_related('instrument').prefetch_related('artists').order_by('-release_date')[:limit]

        context = {
            'request': request,
            'has_stream_access': user_has_stream_access(request.user) if request.user.is_authenticated else False,
            'has_download_access': user_has_all_access(request.user) if request.user.is_authenticated else False,
        }

        return Response({
            "genre": GenreSerializer(genre, context=context).data,
            "albums": AlbumListSerializer(albums, many=True, context=context).data,
            "single_tracks": TrackSerializer(single_tracks, many=True, context=context).data
        }, status=status.HTTP_200_OK)


class InstrumentDetailWithContentAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug, *args, **kwargs):
        instrument = get_object_or_404(Instrument, slug=slug)
        limit = int(request.query_params.get('limit', 20))

        albums = Album.objects.filter(
            tracks__instrument=instrument,
            status=PublishStatus.PUBLISHED,
            album_type=AlbumType.OFFICIAL
        ).distinct().annotate(
            annotated_total_tracks=Count('tracks')
        ).order_by('-release_year')[:limit]

        single_tracks = Track.objects.filter(
            instrument=instrument,
            album__isnull=True,
            status=PublishStatus.PUBLISHED
        ).select_related('genre').prefetch_related('artists').order_by('-release_date')[:limit]

        context = {
            'request': request,
            'has_stream_access': user_has_stream_access(request.user) if request.user.is_authenticated else False,
            'has_download_access': user_has_all_access(request.user) if request.user.is_authenticated else False,
        }

        return Response({
            "instrument": InstrumentSerializer(instrument, context=context).data,
            "albums": AlbumListSerializer(albums, many=True, context=context).data,
            "single_tracks": TrackSerializer(single_tracks, many=True, context=context).data
        }, status=status.HTTP_200_OK)

@method_decorator(never_cache, name='dispatch')
class EditorialPlaylistViewSet(AlbumViewSet):
    album_type = AlbumType.EDITORIAL_PLAYLIST


class LandingPageView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = LandingAlbumSerializer
    pagination_class = LandingPagination

    def get_queryset(self):
        return Album.objects.filter(
            status=PublishStatus.PUBLISHED
        ).prefetch_related('main_artists').order_by('-created_at')


@sync_to_async
def get_album_and_tracks(album_slug):
    album = get_object_or_404(Album, slug=album_slug)
    tracks = list(album.tracks.select_related())
    return album, tracks