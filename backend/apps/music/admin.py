import fcntl
import json
import logging
import os
import re
import shutil
import time
import uuid
import zipfile

import rarfile
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import path
from django.utils.text import get_valid_filename
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.template.response import TemplateResponse
from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.urls import reverse
from django import forms

from .models import (Artist, Album, Track, AlbumArchiveUpload, ArchiveUploadStatus,
                     Genre, Instrument, Label, AlbumCredit)
from .tasks import process_album_archive_task
from .models import AlbumType
from apps.common.storage import local_scratch_storage

logger = logging.getLogger(__name__)

ALLOWED_ARCHIVE_EXTENSIONS = (".zip", ".rar")
MAX_ARCHIVE_UPLOAD_BYTES = getattr(settings, "MAX_ARCHIVE_UPLOAD_BYTES", 10 * 1024 ** 3)  # ۱۰ گیگ



# =========================================================
# Chunked / resumable upload (آپلود تکه‌تکه و قابل ازسرگیری از طریق پنل ادمین)
# مرورگر فایل را به تکه‌های ~۱۰ مگابایتی می‌شکند و هر تکه را با یک درخواست کوچک می‌فرستد؛
# پس درخواست طولانی/۱۰ گیگابایتی وجود ندارد و هر تکه در صورت خطا دوباره ارسال می‌شود.
# =========================================================
CHUNK_SIZE = getattr(settings, "ARCHIVE_UPLOAD_CHUNK_SIZE", 10 * 1024 ** 2)   # باید < FILE_UPLOAD_MAX_MEMORY_SIZE باشد
CHUNK_SESSION_TTL = 2 * 24 * 3600      # جلسه‌های رهاشده بعد از ۲ روز پاک می‌شوند
MIN_FREE_DISK_MARGIN = 1024 ** 3       # حاشیه‌ی امن ۱ گیگ علاوه بر حجم فایل
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def chunks_dir():
    path = local_scratch_storage.path("tmp/chunks")
    os.makedirs(path, exist_ok=True)
    return path


def _session_files(upload_id, base_dir=None):
    base = base_dir or chunks_dir()
    return (
        os.path.join(base, f"{upload_id}.part"),
        os.path.join(base, f"{upload_id}.json"),
        os.path.join(base, f"{upload_id}.done"),
    )


def cleanup_stale_sessions(base_dir=None, now=None):
    base = base_dir or chunks_dir()
    now = time.time() if now is None else now
    for entry in os.scandir(base):
        try:
            if entry.is_file() and now - entry.stat().st_mtime > CHUNK_SESSION_TTL:
                os.remove(entry.path)
        except OSError:
            pass


def chunk_session_init(user_id, album_id, filename, size, base_dir=None):
    """(upload_id, None, None) یا (None, پیام خطا, کد HTTP)"""
    filename = get_valid_filename(os.path.basename(filename or ""))
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_ARCHIVE_EXTENSIONS:
        return None, "فرمت فایل پشتیبانی نمی‌شود. فقط zip و rar مجاز است.", 400
    if size <= 0:
        return None, "فایل خالی است.", 400
    if size > MAX_ARCHIVE_UPLOAD_BYTES:
        limit_gb = MAX_ARCHIVE_UPLOAD_BYTES / 1024 ** 3
        return None, f"حجم فایل بیشتر از سقف مجاز ({limit_gb:.0f} گیگابایت) است.", 413

    base = base_dir or chunks_dir()
    free = shutil.disk_usage(base).free
    if free < size + MIN_FREE_DISK_MARGIN:
        return None, "فضای دیسک سرور برای این آپلود کافی نیست.", 507

    cleanup_stale_sessions(base)
    upload_id = uuid.uuid4().hex
    part, meta_path, _done = _session_files(upload_id, base)
    open(part, "wb").close()
    with open(meta_path, "w") as f:
        json.dump({"user_id": user_id, "album_id": album_id, "filename": filename,
                   "size": size, "created": time.time()}, f)
    return upload_id, None, None


def chunk_session_load(upload_id, user_id, album_id, base_dir=None):
    """meta جلسه، فقط اگر مال همین کاربر و همین آلبوم باشد؛ وگرنه None."""
    if not upload_id or not _UPLOAD_ID_RE.match(upload_id):
        return None
    part, meta_path, _done = _session_files(upload_id, base_dir)
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    if meta.get("user_id") != user_id or meta.get("album_id") != album_id or not os.path.exists(part):
        return None
    return meta


def chunk_append(upload_id, meta, offset, chunk_file, base_dir=None):
    """
    تکه را به انتهای فایل اضافه می‌کند. فقط ارسال ترتیبی پذیرفته می‌شود:
    اگر offset با حجم دریافت‌شده نخواند، 409 به‌همراه received برمی‌گردد تا کلاینت هم‌گام شود.
    (received, None, None) یا (current, پیام, کد)
    """
    part, _meta, _done = _session_files(upload_id, base_dir)
    with open(part, "r+b") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        current = os.fstat(f.fileno()).st_size
        if offset != current:
            return current, "offset با حجم دریافت‌شده نمی‌خواند.", 409
        incoming = getattr(chunk_file, "size", None)
        if incoming is not None and current + incoming > meta["size"]:
            return current, "حجم دریافتی بیشتر از حجم اعلام‌شده است.", 400
        f.seek(0, os.SEEK_END)
        for piece in chunk_file.chunks():
            f.write(piece)
        f.flush()
        return f.tell(), None, None


def chunk_finalize(upload_id, meta, base_dir=None):
    """
    بعد از دریافت همه‌ی تکه‌ها: اعتبارسنجی و انتقال به tmp/archives (rename آنی روی همان mount).
    (rel_name, dst, None, None) یا (None, None, پیام, کد[, received])
    """
    part, meta_path, _done = _session_files(upload_id, base_dir)
    size = os.path.getsize(part)
    if size != meta["size"]:
        return None, None, ("آپلود کامل نیست.", size), 409

    ext = os.path.splitext(meta["filename"])[1].lower()
    if ext == ".zip" and not zipfile.is_zipfile(part):
        return None, None, ("فایل zip ناقص یا خراب است.", size), 400
    if ext == ".rar" and not rarfile.is_rarfile(part):
        return None, None, ("فایل rar ناقص یا خراب است.", size), 400

    rel_name = local_scratch_storage.get_available_name(f"tmp/archives/{meta['filename']}")
    dst = local_scratch_storage.path(rel_name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.rename(part, dst)
    except OSError:
        shutil.move(part, dst)
    return rel_name, dst, None, None

# =========================================================
# Inlines
# =========================================================

class AlbumCreditInline(admin.TabularInline):
    model = AlbumCredit
    extra = 1
    autocomplete_fields = ["artist"]


class TrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = ("title", "artists", "status")
    ordering = ["track_number"]
    show_change_link = True
    autocomplete_fields = ["artists"]


class TrackInlineForLabel(admin.TabularInline):
    model = Track
    extra = 0
    show_change_link = True
    fields = ('title', 'release_date', 'status')
    classes = ('collapse',)


# =========================================================
# Label Admin
# =========================================================
@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'country')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TrackInlineForLabel]
    readonly_fields = ('display_related_albums',)
    ordering = ('-id',)

    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('name', 'slug', 'logo', 'country', 'website', 'description')
        }),
        ('آلبوم‌های مرتبط', {
            'fields': ('display_related_albums',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='آلبوم‌های این لیبل')
    def display_related_albums(self, obj):
        if not obj.pk:
            return "پس از ذخیره لیبل، آلبوم‌ها نمایش داده می‌شوند."
        albums = obj.albums_by_label.all()
        if not albums.exists():
            return "هیچ آلبومی برای این لیبل ثبت نشده است."
        links = []
        for album in albums:
            url = reverse('admin:music_album_change', args=[album.pk])
            link = format_html(
                '<a href="{}" target="_blank" style="display: inline-block; padding: 5px 10px; margin: 3px; background-color: #417690; color: white; border-radius: 4px; text-decoration: none; font-size: 13px;">{}</a>',
                url, album.title
            )
            links.append(link)

        return mark_safe('<div style="display: flex; flex-wrap: wrap;">' + ''.join(links) + '</div>')


# =========================================================
# Artist Admin
# =========================================================
class ArtistAdminForm(forms.ModelForm):
    class Meta:
        model = Artist
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["featured_album"].queryset = Album.objects.filter(
                main_artists=self.instance
            )
        else:
            self.fields["featured_album"].queryset = Album.objects.none()


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    form = ArtistAdminForm

    list_display = (
        "name",
        "nickname",
        "artist_type",
        "era",
        "country",
        "birth_year",
        "death_year"
    )

    list_filter = ("artist_type", "era")
    search_fields = ("name", "nickname", "country", "biography")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("related_artists",)
    ordering = ("-created_at",)

    fieldsets = (
        (_("اطلاعات پایه"), {
            "fields": (
                "name",
                "nickname",
                "slug",
                "artist_type",
                "era",
                "country",
                "image",
                "featured_album"
            )
        }),
        (_("اطلاعات زمانی (تولد / فوت)"), {
            "fields": ("birth_year", "death_year")
        }),
        (_("ارتباطات و جزئیات"), {
            "fields": ("related_artists", "biography")
        }),
        (_("تاریخچه"), {
            "fields": ("created_at", "updated_at")
        }),
    )


# =========================================================
# Track Admin
# =========================================================
@admin.register(Track)
class TrackAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    list_display = ['title', 'get_album_or_single', 'label', 'track_number', 'get_duration', 'status']
    list_filter = ['status', 'album', 'label']
    search_fields = ['title', 'album__title', 'label__name', 'artists__name']

    filter_horizontal = ('artists',)
    autocomplete_fields = ['album', 'genre', 'instrument', 'label']

    list_select_related = ['album', 'label']
    ordering = ['-id']


    @admin.display(description='آلبوم / سینگل', ordering='album__title')
    def get_album_or_single(self, obj):
        if obj.album:
            return obj.album.title
        return "تک‌آهنگ (Single)"

    @admin.display(description='مدت زمان', ordering='duration_ms')
    def get_duration(self, obj):
        if not obj.duration_ms:
            return "00:00"
        seconds = obj.duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"


# =========================================================
# Album Admin
# =========================================================
@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'title_fa', 'created_at', 'label', 'status', 'display_album_type', 'upload_archive_button', 'display_cover_image')
    list_filter = ('status', 'album_type', 'release_year', 'label')
    search_fields = ('title', 'title_fa', 'main_artists__name', 'credits__artist__name', 'label__name')
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ['main_artists', 'label']
    inlines = [AlbumCreditInline, TrackInline]
    ordering = ('-created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('main_artists')

    @admin.display(description=_('نوع انتشار'), ordering='album_type')
    def display_album_type(self, obj):
        if obj.album_type == AlbumType.OFFICIAL:
            return format_html(
                '<span style="white-space: nowrap; display: inline-block; background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
                obj.get_album_type_display()
            )
        elif obj.album_type == AlbumType.EDITORIAL_PLAYLIST:
            return format_html(
                '<span style="white-space: nowrap; display: inline-block; background-color: #dc3545; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
                obj.get_album_type_display()
            )
        return format_html(
            '<span style="white-space: nowrap; display: inline-block;">{}</span>',
            obj.get_album_type_display()
        )

    def display_cover_image(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" width="50" height="50" style="border-radius:4px;"/>', obj.cover_image.url)
        return _("بدون کاور")

    display_cover_image.short_description = _("کاور آلبوم")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.cover_image and change:
            tracks_to_update = Track.objects.filter(album=obj, cover_image__isnull=True)
            updated_count = tracks_to_update.update(cover_image=obj.cover_image.name)
            if updated_count > 0:
                messages.success(request, _(f"کاور آلبوم به {updated_count} ترک اختصاص داده شد."))

    def upload_archive_button(self, obj):
        url = reverse('admin:album_batch_upload', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="white-space: nowrap; display: inline-block; background:#389dcf; color:white; padding:5px 10px; border-radius:4px; text-decoration:none;">آپلود فایل زیپ</a>',
            url
        )

    upload_archive_button.short_description = "آپلود آرشیو"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:album_id>/batch-upload/', self.admin_site.admin_view(self.batch_upload_view),
                 name='album_batch_upload'),
            path('<int:album_id>/chunk-upload/', self.admin_site.admin_view(self.chunk_upload_view),
                 name='album_chunk_upload'),
            path('upload-progress/<int:upload_id>/', self.admin_site.admin_view(self.upload_progress_api),
                 name='album_upload_progress'),
        ]
        return custom_urls + urls

    def batch_upload_view(self, request, album_id):
        album = self.get_object(request, album_id)
        if album is None:
            raise Http404("آلبوم یافت نشد.")
        if not self.has_change_permission(request, album):
            raise PermissionDenied

        if request.method == 'POST':
            archive_file = request.FILES.get('archive_file')
            if not archive_file:
                return JsonResponse({'error': 'No file provided.'}, status=400)

            # اعتبارسنجی زودهنگام: قبل از ساخت رکورد و ارسال تسک به Celery
            ext = os.path.splitext(archive_file.name)[1].lower()
            if ext not in ALLOWED_ARCHIVE_EXTENSIONS:
                return JsonResponse({'error': 'فرمت فایل پشتیبانی نمی‌شود. فقط zip و rar مجاز است.'}, status=400)
            if archive_file.size > MAX_ARCHIVE_UPLOAD_BYTES:
                limit_gb = MAX_ARCHIVE_UPLOAD_BYTES / 1024 ** 3
                return JsonResponse({'error': f'حجم فایل بیشتر از سقف مجاز ({limit_gb:.0f} گیگابایت) است.'}, status=413)

            upload_record = AlbumArchiveUpload.objects.create(
                album=album,
                archive_file=archive_file,
                status=ArchiveUploadStatus.PENDING,
                progress=0
            )
            task = process_album_archive_task.delay(upload_record.id)
            # فقط task_id را آپدیت می‌کنیم؛ save() کامل ممکن بود status/progress که تسک
            # همین حالا تغییر داده را به PENDING/0 برگرداند (race با Celery).
            AlbumArchiveUpload.objects.filter(pk=upload_record.pk).update(task_id=task.id)

            progress_url = reverse('admin:album_upload_progress', args=[upload_record.id])
            return JsonResponse({
                'success': True,
                'upload_record_id': upload_record.id,
                'progress_url': progress_url
            })
        context = dict(
            self.admin_site.each_context(request),
            album=album,
        )
        return TemplateResponse(request, "admin/music/track/batch_zip_upload.html", context)

    def chunk_upload_view(self, request, album_id):
        """
        GET  ?upload_id=...                       -> وضعیت جلسه (برای ازسرگیری)
        POST action=init     filename,size        -> شروع جلسه
        POST action=chunk    upload_id,offset,chunk -> افزودن یک تکه
        POST action=complete upload_id            -> نهایی‌سازی و ثبت تسک Celery
        POST action=abort    upload_id            -> لغو و پاک‌سازی
        """
        album = self.get_object(request, album_id)
        if album is None:
            raise Http404("آلبوم یافت نشد.")
        if not self.has_change_permission(request, album):
            raise PermissionDenied

        user_id = request.user.pk

        if request.method == 'GET':
            upload_id = request.GET.get('upload_id', '')
            meta = chunk_session_load(upload_id, user_id, album_id)
            if meta is None:
                return JsonResponse({'error': 'جلسه‌ی آپلود پیدا نشد.'}, status=404)
            part, _m, _d = _session_files(upload_id)
            return JsonResponse({'ok': True, 'received': os.path.getsize(part), 'size': meta['size'],
                                 'chunk_size': CHUNK_SIZE})

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed.'}, status=405)

        action = request.POST.get('action')

        if action == 'init':
            try:
                size = int(request.POST.get('size', '0'))
            except ValueError:
                return JsonResponse({'error': 'حجم نامعتبر است.'}, status=400)
            upload_id, error, status = chunk_session_init(
                user_id, album_id, request.POST.get('filename', ''), size)
            if error:
                return JsonResponse({'error': error}, status=status)
            return JsonResponse({'ok': True, 'upload_id': upload_id, 'chunk_size': CHUNK_SIZE})

        upload_id = request.POST.get('upload_id', '')

        if action == 'complete':
            # اگر پاسخ قبلی در شبکه گم شده باشد، همین نتیجه‌ی قبلی را برمی‌گردانیم (idempotent)
            if _UPLOAD_ID_RE.match(upload_id):
                _p, _m, done_path = _session_files(upload_id)
                try:
                    with open(done_path) as f:
                        done = json.load(f)
                    if done.get('user_id') == user_id and done.get('album_id') == album_id:
                        return JsonResponse({'success': True, 'upload_record_id': done['upload_record_id'],
                                             'progress_url': done['progress_url']})
                except (OSError, ValueError):
                    pass

        meta = chunk_session_load(upload_id, user_id, album_id)
        if meta is None:
            return JsonResponse({'error': 'جلسه‌ی آپلود پیدا نشد (ممکن است منقضی شده باشد).'}, status=404)

        if action == 'chunk':
            chunk = request.FILES.get('chunk')
            try:
                offset = int(request.POST.get('offset', ''))
            except ValueError:
                return JsonResponse({'error': 'offset نامعتبر است.'}, status=400)
            if chunk is None or offset < 0:
                return JsonResponse({'error': 'تکه‌ی فایل ارسال نشده است.'}, status=400)
            received, error, status = chunk_append(upload_id, meta, offset, chunk)
            if error:
                return JsonResponse({'error': error, 'received': received}, status=status)
            return JsonResponse({'ok': True, 'received': received})

        if action == 'complete':
            rel_name, dst, error, status = chunk_finalize(upload_id, meta)
            if error:
                message, received = error
                return JsonResponse({'error': message, 'received': received}, status=status)

            part, meta_path, done_path = _session_files(upload_id)
            upload_record = None
            try:
                upload_record = AlbumArchiveUpload.objects.create(
                    album=album, archive_file=rel_name,
                    status=ArchiveUploadStatus.PENDING, progress=0,
                )
                task = process_album_archive_task.delay(upload_record.id)
            except Exception:
                logger.exception("Failed to register chunked upload %s", upload_id)
                if upload_record is not None:
                    upload_record.delete()
                try:
                    shutil.move(dst, part)  # فایل سالم می‌ماند؛ کاربر می‌تواند دوباره «نهایی‌سازی» کند
                except Exception:
                    logger.exception("Failed to restore %s", dst)
                return JsonResponse({'error': 'ثبت پردازش ناموفق بود؛ لاگ سرور را بررسی کنید.'}, status=500)

            AlbumArchiveUpload.objects.filter(pk=upload_record.pk).update(task_id=task.id)
            progress_url = reverse('admin:album_upload_progress', args=[upload_record.id])
            try:
                with open(done_path, 'w') as f:
                    json.dump({'user_id': user_id, 'album_id': album_id,
                               'upload_record_id': upload_record.id, 'progress_url': progress_url}, f)
                os.remove(meta_path)
            except OSError:
                logger.exception("Failed to write done marker for %s", upload_id)
            return JsonResponse({'success': True, 'upload_record_id': upload_record.id,
                                 'progress_url': progress_url})

        if action == 'abort':
            for p in _session_files(upload_id)[:2]:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return JsonResponse({'ok': True})

        return JsonResponse({'error': 'action نامعتبر است.'}, status=400)

    def upload_progress_api(self, request, upload_id):
        try:
            record = AlbumArchiveUpload.objects.get(id=upload_id)
            return JsonResponse({
                'status': record.status,
                'progress': record.progress,
                'error_log': record.error_log
            })
        except AlbumArchiveUpload.DoesNotExist:
            return JsonResponse({'status': 'ERROR', 'error_log': 'Record not found'}, status=404)

# =========================================================
# Genre & Instrument Admin
# =========================================================
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)