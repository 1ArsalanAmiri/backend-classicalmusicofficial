from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from .models import Playlist, PlaylistTrack


class PlaylistTrackInline(admin.TabularInline):
    model = PlaylistTrack
    extra = 1
    autocomplete_fields = ['track']
    ordering = ['order']
    readonly_fields = ['added_at']


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'title_fa',
        'tracks_count',
        'duration_display',
        'created_at',
        'cover_preview_thumbnail'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['title', 'title_fa', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PlaylistTrackInline]
    date_hierarchy = 'created_at'

    readonly_fields = ['created_at', 'updated_at', 'cover_image_preview']

    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('title', 'title_fa', 'slug', 'description')
        }),
        ('رسانه (Media)', {
            'fields': ('cover_image', 'cover_image_preview')
        }),
        ('تنظیمات و تاریخ‌ها', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # حذف owner از select_related به دلیل عدم وجود در مدل جدید
        qs = qs.annotate(
            admin_total_tracks=Count('playlist_tracks', distinct=True),
            admin_total_duration=Sum('tracks__duration_ms')
        )
        return qs

    @admin.display(description='تعداد ترک‌ها', ordering='admin_total_tracks')
    def tracks_count(self, obj):
        return getattr(obj, 'admin_total_tracks', 0)

    @admin.display(description='مدت زمان کل', ordering='admin_total_duration')
    def duration_display(self, obj):
        total_ms = getattr(obj, 'admin_total_duration', 0) or 0
        if not total_ms:
            return "00:00"

        minutes = total_ms // 60000
        seconds = (total_ms % 60000) // 1000
        return f"{minutes}:{seconds:02d}"

    @admin.display(description='کاور')
    def cover_preview_thumbnail(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 4px; object-fit: cover;" />',
                obj.cover_image.url
            )
        return "-"

    @admin.display(description='پیش‌نمایش تصویر')
    def cover_image_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />',
                obj.cover_image.url
            )
        return "تصویری آپلود نشده است"


@admin.register(PlaylistTrack)
class PlaylistTrackAdmin(admin.ModelAdmin):
    list_display = ['playlist', 'track', 'added_at']
    list_filter = ['added_at']
    search_fields = ['playlist__title', 'track__title', 'track__slug']
    autocomplete_fields = ['playlist', 'track']
    ordering = ['playlist', 'order']
    list_select_related = ['playlist', 'track']
