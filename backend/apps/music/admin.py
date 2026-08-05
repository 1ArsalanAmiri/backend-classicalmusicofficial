from django.contrib import admin, messages
from django.urls import path
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.template.response import TemplateResponse
from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.urls import reverse

from .models import (Artist, Album, Track, AlbumArchiveUpload, ArchiveUploadStatus,
                     Genre, Instrument, Label, AlbumCredit)
from .tasks import process_album_archive_task
from .models import AlbumType

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
@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ("name", "nickname" ,"artist_type", "era", "country", "birth_year", "death_year")
    list_filter = ("artist_type", "era")
    search_fields = ("name", "nickname", "country", "biography")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("related_artists",)

    fieldsets = (
        (_("اطلاعات پایه"), {
            "fields": ("name", "nickname", "slug", "artist_type", "era", "country", "image")
        }),
        (_("اطلاعات زمانی (تولد / فوت)"), {
            "fields": ("birth_year", "death_year")
        }),
        (_("ارتباطات و جزئیات"), {
            "fields": ("related_artists", "biography",)
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
    list_display = ('title', 'title_fa', 'display_main_artists', 'label', 'status', 'display_album_type', 'upload_archive_button', 'display_cover_image')

    list_filter = ('status', 'album_type', 'release_year', 'label')

    search_fields = ('title', 'title_fa', 'main_artists__name', 'credits__artist__name', 'label__name')
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ['main_artists', 'label']
    inlines = [AlbumCreditInline, TrackInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('main_artists')

    @admin.display(description=_('نوع انتشار'), ordering='album_type')
    def display_album_type(self, obj):
        if obj.album_type == AlbumType.OFFICIAL:
            return format_html('<span style="background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>', obj.get_album_type_display())
        elif obj.album_type == AlbumType.EDITORIAL_PLAYLIST:
            return format_html('<span style="background-color: #dc3545; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>', obj.get_album_type_display())
        return obj.get_album_type_display()

    @admin.display(description=_('آرتیست‌های اصلی'))
    def display_main_artists(self, obj):
        artists = obj.main_artists.all()
        if artists.exists():
            return ", ".join([artist.name for artist in artists])
        return "-"

# =========================================================
# Genre & Instrument Admin
# =========================================================
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)
