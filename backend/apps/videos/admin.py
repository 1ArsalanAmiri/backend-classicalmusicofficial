from django.contrib import admin
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
