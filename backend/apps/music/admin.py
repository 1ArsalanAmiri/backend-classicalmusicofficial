from django.contrib import admin , messages
from django.urls import path
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Artist, Album, Track, AlbumArchiveUpload, ArchiveUploadStatus, Genre, Instrument
from django.http import JsonResponse
from django.template.response import TemplateResponse
from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.urls import reverse
from .tasks import process_album_archive_task


# =========================================================
# Artist Admin
# =========================================================

@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ("name", "artist_type", "era", "country", "created_at")
    list_filter = ("artist_type", "era")
    search_fields = ("name", "country", "biography")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (_("اطلاعات پایه"), {
            "fields": ("name", "slug", "artist_type", "era", "country", "image")
        }),
        (_("جزئیات"), {
            "fields": ("biography",)
        }),
        (_("تاریخچه"), {
            "fields": ("created_at", "updated_at")
        }),
    )

# =========================================================
# Track Inline for Album Admin
# =========================================================

class TrackInline(admin.TabularInline):

    model = Track
    extra = 0
    fields = ("track_number", "title", "audio_file", "duration_ms", "composer", "singer", "status")
    autocomplete_fields = ["composer", "singer"]
    ordering = ["track_number"]

# =========================================================
# Track Admin (Standalone)
# =========================================================

@admin.register(Track)
class TrackAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    list_display = ['title', 'get_album_or_single', 'track_number', 'get_duration', 'status']
    list_filter = ['status', 'album']
    search_fields = ['title', 'album__title']

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



@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'composer' ,'status', 'upload_archive_button', 'display_cover_image')
    list_filter = ('status', 'release_date')
    search_fields = ('title', 'composer', 'conductor', 'orchestra', 'soloist', 'ensemble')
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")

    def display_cover_image(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.cover_image.url)
        return _("بدون کاور")
    display_cover_image.short_description = _("کاور آلبوم")


    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if obj.cover_image and change:
            tracks_to_update = Track.objects.filter(album=obj, cover_image__isnull=True)
            for track in tracks_to_update:
                track.save()
            messages.success(request, _(f"کاور آلبوم به {tracks_to_update.count()} ترک اختصاص داده شد."))

        elif not obj.cover_image and change:
             pass


    def upload_archive_button(self, obj):
        url = reverse('admin:album_batch_upload', args=[obj.pk])
        return format_html('<a class="button" href="{}">آپلود گروهی ترک‌ها (ZIP/RAR)</a>', url)
    upload_archive_button.short_description = "آپلود آرشیو"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:album_id>/batch-upload/', self.admin_site.admin_view(self.batch_upload_view),
                 name='album_batch_upload'),
            path('upload-progress/<int:upload_id>/', self.admin_site.admin_view(self.upload_progress_api),
                 name='album_upload_progress'),
        ]
        return custom_urls + urls

    def batch_upload_view(self, request, album_id):
        album = self.get_object(request, album_id)
        if request.method == 'POST' and request.FILES.get('archive_file'):
            archive_file = request.FILES['archive_file']
            upload_record = AlbumArchiveUpload.objects.create(
                album=album,
                archive_file=archive_file,
                status=ArchiveUploadStatus.PENDING,
                progress=0
            )
            task = process_album_archive_task.delay(upload_record.id)
            upload_record.task_id = task.id
            upload_record.save()

            progress_url = reverse('admin:album_upload_progress', args=[upload_record.id])
            context = dict(
                self.admin_site.each_context(request),
                album=album,
                upload_record_id=upload_record.id,
                progress_url=progress_url,
                is_uploading=True,
            )
            return TemplateResponse(request, "admin/music/track/batch_zip_upload.html", context)

        context = dict(
            self.admin_site.each_context(request),
            album=album,
            is_uploading=False,
        )
        return TemplateResponse(request, "admin/music/track/batch_zip_upload.html", context)

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



@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "name",
    )

    fieldsets = (
        ("اطلاعات ژانر", {
            "fields": (
                "name",
                "slug",
            )
        }),
        ("اطلاعات سیستمی", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "name",
    )

    fieldsets = (
        ("اطلاعات ساز", {
            "fields": (
                "name",
                "slug",
            )
        }),
        ("اطلاعات سیستمی", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )
