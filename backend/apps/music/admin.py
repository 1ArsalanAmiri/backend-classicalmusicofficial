from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.template.response import TemplateResponse
from django.http import JsonResponse

# فرض بر این است که مدل‌ها در همین اپلیکیشن قرار دارند
from .models import Album, Track, Label, AlbumCredit
from .tasks import process_album_archive_task


# در صورتی که از پکیج‌های اکستنشن (مثل django-admin-extra-buttons) استفاده می‌کنید:
# from admin_extra_buttons.mixins import ExtraButtonsMixin
class ExtraButtonsMixin:
    """کلاس فرضی در صورتی که به صورت سفارشی پیاده‌سازی کرده‌اید"""
    pass


# ==========================================
# Inlines
# ==========================================
class TrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = ['track_number', 'title', 'audio_file', 'duration', 'status']
    # در صورت نیاز برای فیلدهای طولانی یا روابط
    # autocomplete_fields = ['artists']


class AlbumCreditInline(admin.TabularInline):
    model = AlbumCredit
    extra = 0


# ==========================================
# Label Admin
# ==========================================
@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_related_albums']
    search_fields = ['name']

    @admin.display(description='آلبوم‌های این لیبل')
    def display_related_albums(self, obj):
        if not obj.pk:
            return "پس از ذخیره لیبل، آلبوم‌ها نمایش داده می‌شوند."

        # فرض بر این است که related_name در مدل آلبوم albums_by_label تعریف شده
        albums = obj.albums_by_label.all()

        if not albums.exists():
            return "هیچ آلبومی برای این لیبل ثبت نشده است."

        links = []
        for album in albums:
            url = reverse('admin:music_album_change', args=[album.pk])
            # [تغییر امنیتی اعمال شده]: استفاده از format_html به جای f-string برای جلوگیری از XSS
            link = format_html(
                '<a href="{}" target="_blank" style="display: inline-block; padding: 5px 10px; margin: 3px; background-color: #417690; color: white; border-radius: 4px; text-decoration: none; font-size: 13px;">{}</a>',
                url, album.title
            )
            links.append(link)

        return mark_safe('<div style="display: flex; flex-wrap: wrap;">' + ''.join(links) + '</div>')


# ==========================================
# Album Admin
# ==========================================
@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ['title', 'release_date', 'display_main_artists']
    autocomplete_fields = ['main_artists', 'genre', 'label']
    inlines = [TrackInline, AlbumCreditInline]
    search_fields = ['title']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # [تغییر پرفورمنس اعمال شده]: جلوگیری از N+1 Query در لیست آلبوم‌ها
        return qs.prefetch_related('main_artists')

    @admin.display(description='هنرمندان اصلی')
    def display_main_artists(self, obj):
        return ", ".join([artist.name for artist in obj.main_artists.all()])

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # منطق هوشمندانه شما برای کپی کردن کاور آلبوم روی ترک‌های فاقد کاور
        if obj.cover:
            tracks_to_update = obj.tracks.filter(cover__exact='')
            if tracks_to_update.exists():
                for track in tracks_to_update:
                    track.cover = obj.cover
                # استفاده از bulk_update برای جلوگیری از هیت‌های اضافی به دیتابیس
                Track.objects.bulk_update(tracks_to_update, ['cover'])

    # -- Custom Admin Views for Bulk Upload --
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'batch-upload/',
                self.admin_site.admin_view(self.batch_upload_view),
                name='album_batch_upload'
            ),
            path(
                'upload-progress/',
                self.admin_site.admin_view(self.upload_progress_api),
                name='album_upload_progress'
            ),
        ]
        return custom_urls + urls

    def batch_upload_view(self, request):
        context = dict(
            self.admin_site.each_context(request),
            title="آپلود گروهی / آرشیو آلبوم",
        )
        # مسیر تمپلیت آپلود گروهی
        return TemplateResponse(request, "admin/music/album/batch_upload.html", context)

    def upload_progress_api(self, request):
        # این ویو توسط جاوااسکریپت در فرانت‌اند برای دریافت پراگرس تسک سلری فراخوانی می‌شود
        # در اینجا می‌توانید به Redis یا Celery Task State متصل شوید
        task_id = request.GET.get('task_id')
        # ... منطق دریافت وضعیت تسک ...
        return JsonResponse({'status': 'processing', 'progress': 0})


# ==========================================
# Track Admin
# ==========================================
@admin.register(Track)
class TrackAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    list_display = ['title', 'get_album_or_single', 'label', 'track_number', 'get_duration', 'status']

    list_select_related = ['album', 'label']

    autocomplete_fields = ['album', 'artists', 'genre', 'label']
    search_fields = ['title', 'album__title']
    list_filter = ['status', 'genre']

    @admin.display(description='آلبوم / تک‌آهنگ')
    def get_album_or_single(self, obj):
        return obj.album.title if obj.album else "تک‌آهنگ"

    @admin.display(description='مدت زمان')
    def get_duration(self, obj):
        return obj.duration
