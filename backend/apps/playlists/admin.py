from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.utils.translation import gettext_lazy as _
from .models import Playlist, PlaylistItem


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 1
    autocomplete_fields = ['track']
    ordering = ['order']
    readonly_fields = ['created_at']


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'title_fa',
        'user',
        'tracks_count',
        'duration_display',
        'cover_preview_thumbnail',
        'created_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['title', 'title_fa', 'slug', 'user__username', 'user__email']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PlaylistItemInline]
    date_hierarchy = 'created_at'
    autocomplete_fields = ['user']
    readonly_fields = ['created_at', 'updated_at', 'cover_image_preview']

    fieldsets = (
        (_('اطلاعات پایه'), {
            'fields': ('title', 'title_fa', 'slug', 'description', 'user')
        }),
        (_('رسانه (Media)'), {
            'fields': ('cover_image', 'cover_image_preview')
        }),
        (_('تنظیمات و تاریخ‌ها'), {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user').annotate(
            admin_total_tracks=Count('items', distinct=True),
            admin_total_duration=Sum('items__track__duration_ms')
        )

    @admin.display(description=_('تعداد ترک‌ها'), ordering='admin_total_tracks')
    def tracks_count(self, obj):
        return getattr(obj, 'admin_total_tracks', 0)

    @admin.display(description=_('مدت زمان کل'), ordering='admin_total_duration')
    def duration_display(self, obj):
        total_ms = getattr(obj, 'admin_total_duration', 0) or 0
        if not total_ms:
            return "00:00"

        total_seconds = total_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        hours = minutes // 60
        minutes = minutes % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @admin.display(description=_('کاور'))
    def cover_preview_thumbnail(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 4px; object-fit: cover;" />',
                obj.cover_image.url
            )
        return "-"

    @admin.display(description=_('پیش‌نمایش تصویر'))
    def cover_image_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />',
                obj.cover_image.url
            )
        return "تصویری آپلود نشده است"