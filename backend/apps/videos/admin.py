from django.contrib import admin
from django.db import transaction
from .tasks import convert_video_to_hls
from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'recording_year', 'duration_seconds', 'view_count']
    list_filter = ['status', 'era', 'recording_year']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ['artists']
    readonly_fields = ['view_count', 'likes_count']
    list_editable = ['status']

    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('title', 'slug', 'artists', 'era', 'recording_year')
        }),
        ('رسانه', {
            'fields': ('video_file', 'cover_image', 'duration_seconds')
        }),
        ('آمار و وضعیت', {
            'fields': ('status', 'view_count', 'likes_count')
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.video_file and obj.status == 'processing' and not obj.hls_file:
            transaction.on_commit(lambda: convert_video_to_hls.delay(obj.id))
