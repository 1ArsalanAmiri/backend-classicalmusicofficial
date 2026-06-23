from django.contrib import admin, messages
from django.urls import path
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from .models import Artist, Album, Track, AlbumArchiveUpload, ArchiveUploadStatus, Genre, Instrument, Label
from django.http import JsonResponse
from django.template.response import TemplateResponse
from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.urls import reverse
from .tasks import process_album_archive_task


# =========================================================
# Track Inline for Album Admin
# =========================================================
class TrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = ("track_number", "title", "audio_file", "duration_ms", "composer", "singer", "status")
    autocomplete_fields = ["composer", "singer"]
    ordering = ["track_number"]


class TrackInlineForLabel(admin.TabularInline):
    model = Track
    extra = 0
    show_change_link = True
    fields = ('title', 'release_date', 'status')
    classes = ('collapse',)
    # readonly_fields = ('title', 'release_date', 'is_published')


# =========================================================
# Label Admin (لیبل / ناشر)
# =========================================================
@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'country')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

    inlines = [TrackInlineForLabel]

    readonly_fields = ('display_related_albums',)

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

        albums = obj.albums.all()

        if not albums.exists():
            return "هیچ آلبومی برای این لیبل ثبت نشده است."

        links = []
        for album in albums:
            url = reverse('admin:music_album_change', args=[album.pk])
            link = f'<a href="{url}" target="_blank" style="display: inline-block; padding: 5px 10px; margin: 3px; background-color: #417690; color: white; border-radius: 4px; text-decoration: none; font-size: 13px;">{album.title}</a>'
            links.append(link)

        return mark_safe('<div style="display: flex; flex-wrap: wrap;">' + ''.join(links) + '</div>')

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
# Track Admin (Standalone)
# =========================================================
@admin.register(Track)
class TrackAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    # فیلد label به نمایش اضافه شد
    list_display = ['title', 'get_album_or_single', 'label', 'track_number', 'get_duration', 'status']
    # فیلتر بر اساس لیبل اضافه شد
    list_filter = ['status', 'album', 'label']
    search_fields = ['title', 'album__title', 'label__name']

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
    list_display = ('title', 'composer', 'label', 'status', 'upload_archive_button', 'display_cover_image')
    list_filter = ('status', 'release_date', 'label')
    search_fields = ('title', 'composer', 'conductor', 'orchestra', 'soloist', 'ensemble', 'label__name')
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ['artist']


    inlines = [TrackInline]

    def display_cover_image(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.cover_image.url)
        return _("بدون کاور")

    display_cover_image.short_description = _("کاور آلبوم")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if obj.cover_image and change:
            tracks_to_update = Track.objects.filter(album=obj, cover_image__isnull=True)
            updated_count = tracks_to_update.update(cover_image=obj.cover_image)
            if updated_count > 0:
                messages.success(request, _(f"کاور آلبوم به {updated_count} ترک اختصاص داده شد."))

    def upload_archive_button(self, obj):
        url = reverse('admin:album_batch_upload', args=[obj.pk])
        return format_html('<a class="button" href="{}">Bulk Upload</a>', url)

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

        if request.method == 'POST':
            archive_file = request.FILES.get('archive_file')
            if not archive_file:
                return JsonResponse({'error': 'No file provided.'}, status=400)

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
# Genre Admin
# =========================================================
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)

    fieldsets = (
        ("اطلاعات ژانر", {"fields": ("name", "slug")}),
        ("اطلاعات سیستمی", {"fields": ("created_at", "updated_at")}),
    )

# =========================================================
# Instrument Admin
# =========================================================
@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)

    fieldsets = (
        ("اطلاعات ساز", {"fields": ("name", "slug")}),
        ("اطلاعات سیستمی", {"fields": ("created_at", "updated_at")}),
    )


