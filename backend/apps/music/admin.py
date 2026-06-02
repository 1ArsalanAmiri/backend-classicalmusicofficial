# apps/music/admin.py
from __future__ import annotations

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    Album,
    AlbumType,
    Artist,
    ArtistType,
    Composer,
    CreditRole,
    Era,
    Genre,
    Label,
    PublishStatus,
    Recording,
    RecordingCredit,
    RecordingType,
    Track,
    Work,
    WorkCatalogRef,
    WorkType,
)

# =========================================================
# Shared admin helpers
# =========================================================

@admin.action(description=_("انتشار انتخاب‌شده‌ها"))
def make_published(modeladmin, request, queryset):
    queryset.update(status=PublishStatus.PUBLISHED)


@admin.action(description=_("پیش‌نویس کردن انتخاب‌شده‌ها"))
def make_draft(modeladmin, request, queryset):
    queryset.update(status=PublishStatus.DRAFT)


@admin.action(description=_("آرشیو کردن انتخاب‌شده‌ها"))
def make_archived(modeladmin, request, queryset):
    queryset.update(status=PublishStatus.ARCHIVED)


class TimestampedAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50


# =========================================================
# Taxonomies
# =========================================================

@admin.register(Genre)
class GenreAdmin(TimestampedAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Era)
class EraAdmin(TimestampedAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(WorkType)
class WorkTypeAdmin(TimestampedAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Label)
class LabelAdmin(TimestampedAdmin):
    list_display = ("name", "slug", "website_link", "created_at")
    search_fields = ("name", "slug", "website")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def website_link(self, obj: Label):
        if not obj.website:
            return "-"
        return format_html('<a href="{}" target="_blank" rel="noopener">link</a>', obj.website)
    website_link.short_description = _("وب‌سایت")


# =========================================================
# Artists / composers
# =========================================================

@admin.register(Artist)
class ArtistAdmin(TimestampedAdmin):
    list_display = (
        "name",
        "artist_type",
        "country",
        "is_active",
        "is_featured",
        "status",
        "genres_count",
        "created_at",
    )
    list_filter = (
        "artist_type",
        "is_active",
        "is_featured",
        "status",
        ("genres", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("name", "sort_name", "slug", "country")
    autocomplete_fields = ("genres",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_name", "name")
    actions = (make_published, make_draft, make_archived)

    fieldsets = (
        (_("اطلاعات اصلی"), {
            "fields": ("name", "sort_name", "slug", "artist_type", "country", "image")
        }),
        (_("زندگی‌نامه"), {
            "fields": ("birth_date", "death_date", "short_bio"),
        }),
        (_("وضعیت"), {
            "fields": ("is_active", "is_featured", "status", "genres"),
        }),
        (_("سیستمی"), {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_genres_count=Count("genres", distinct=True))

    def genres_count(self, obj: Artist):
        return getattr(obj, "_genres_count", 0)
    genres_count.short_description = _("تعداد ژانر")
    genres_count.admin_order_field = "_genres_count"


@admin.register(Composer)
class ComposerAdmin(TimestampedAdmin):
    list_display = ("artist", "era", "is_featured", "created_at")
    list_filter = ("era", "is_featured")
    search_fields = ("artist__name", "artist__sort_name")
    autocomplete_fields = ("artist", "era")
    ordering = ("artist__sort_name", "artist__name")


# =========================================================
# Works
# =========================================================

class WorkCatalogRefInline(admin.TabularInline):
    model = WorkCatalogRef
    extra = 1
    fields = ("number",)
    autocomplete_fields = ()
    show_change_link = True


@admin.register(Work)
class WorkAdmin(TimestampedAdmin):
    list_display = (
        "title",
        "composer",
        "era",
        "genre",
        "work_type",
        "composition_year",
        "is_featured",
        "status",
        "recordings_count",
        "created_at",
    )
    list_filter = (
        "status",
        "is_featured",
        ("era", admin.RelatedOnlyFieldListFilter),
        ("genre", admin.RelatedOnlyFieldListFilter),
        ("work_type", admin.RelatedOnlyFieldListFilter),
        ("composer", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "title",
        "full_title",
        "normalized_title",
        "slug",
        "composer__artist__name",
        "composer__artist__sort_name",
    )
    autocomplete_fields = ("composer", "genre", "work_type", "era", "parent_work")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (WorkCatalogRefInline,)
    actions = (make_published, make_draft, make_archived)

    fieldsets = (
        (_("مشخصات"), {
            "fields": ("composer", "title", "full_title", "slug", "parent_work"),
        }),
        (_("طبقه‌بندی"), {
            "fields": ("genre", "work_type", "era", "composition_year"),
        }),
        (_("وضعیت"), {
            "fields": ("is_featured", "status"),
        }),
        (_("توضیحات"), {
            "fields": ("description",),
        }),
        (_("سیستمی"), {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_recordings_count=Count("recordings", distinct=True))

    def recordings_count(self, obj: Work):
        return getattr(obj, "_recordings_count", 0)
    recordings_count.short_description = _("تعداد ضبط")
    recordings_count.admin_order_field = "_recordings_count"


@admin.register(WorkCatalogRef)
class WorkCatalogRefAdmin(TimestampedAdmin):
    list_display = ("work", "number", "created_at")
    search_fields = ("number", "work__title", "work__composer__artist__name")
    autocomplete_fields = ("work",)
    ordering = ("number",)


# =========================================================
# Recordings
# =========================================================

class RecordingCreditInline(admin.TabularInline):
    model = RecordingCredit
    extra = 1
    fields = ("artist", "role", "credit_order", "is_primary")
    autocomplete_fields = ("artist",)
    ordering = ("credit_order", "id")
    show_change_link = True


@admin.register(Recording)
class RecordingAdmin(TimestampedAdmin):
    list_display = (
        "display_title",
        "work",
        "recording_type",
        "label",
        "release_date",
        "is_complete_work",
        "is_featured",
        "status",
        "tracks_count",
        "created_at",
    )
    list_filter = (
        "recording_type",
        "status",
        "is_featured",
        "is_complete_work",
        ("label", admin.RelatedOnlyFieldListFilter),
        ("work", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "title_override",
        "work__title",
        "work__full_title",
        "work__composer__artist__name",
        "label__name",
    )
    autocomplete_fields = ("work", "label")
    inlines = (RecordingCreditInline,)
    actions = (make_published, make_draft, make_archived)
    date_hierarchy = "release_date"
    ordering = ("-release_date", "-id")

    fieldsets = (
        (_("اصلی"), {
            "fields": ("work", "title_override", "recording_type"),
        }),
        (_("تاریخ‌ها"), {
            "fields": ("recording_date", "release_date"),
        }),
        (_("انتشار"), {
            "fields": ("label", "is_complete_work", "duration_ms"),
        }),
        (_("امتیازدهی"), {
            "fields": ("popularity", "is_featured", "status"),
        }),
        (_("سیستمی"), {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_tracks_count=Count("tracks", distinct=True))

    def tracks_count(self, obj: Recording):
        return getattr(obj, "_tracks_count", 0)
    tracks_count.short_description = _("تعداد ترک")
    tracks_count.admin_order_field = "_tracks_count"


@admin.register(RecordingCredit)
class RecordingCreditAdmin(TimestampedAdmin):
    list_display = ("recording", "artist", "role", "credit_order", "is_primary", "created_at")
    list_filter = ("role", "is_primary")
    search_fields = ("recording__work__title", "recording__work__composer__artist__name", "artist__name")
    autocomplete_fields = ("recording", "artist")
    ordering = ("recording", "credit_order", "id")


# =========================================================
# Albums / tracks
# =========================================================

class TrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = (
        "disc_number",
        "track_number",
        "sequence_order",
        "recording",
        "title_override",
        "duration_ms",
        "is_premium",
        "is_streamable",
        "status",
    )
    autocomplete_fields = ("recording",)
    show_change_link = True
    ordering = ("disc_number", "track_number", "sequence_order", "id")


@admin.register(Album)
class AlbumAdmin(TimestampedAdmin):
    list_display = (
        "title",
        "album_type",
        "label",
        "release_date",
        "is_featured",
        "status",
        "tracks_count",
        "created_at",
    )
    list_filter = (
        "album_type",
        "status",
        "is_featured",
        ("label", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("title", "slug", "label__name")
    autocomplete_fields = ("label",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = (TrackInline,)
    actions = (make_published, make_draft, make_archived)
    date_hierarchy = "release_date"
    ordering = ("-release_date", "title")

    fieldsets = (
        (_("اصلی"), {"fields": ("title", "slug", "album_type", "label", "release_date")}),
        (_("محتوا"), {"fields": ("cover_image", "description", "editorial_note")}),
        (_("وضعیت"), {"fields": ("is_featured", "popularity", "status")}),
        (_("سیستمی"), {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_tracks_count=Count("tracks", distinct=True))

    def tracks_count(self, obj: Album):
        return getattr(obj, "_tracks_count", 0)
    tracks_count.short_description = _("تعداد ترک")
    tracks_count.admin_order_field = "_tracks_count"


@admin.register(Track)
class TrackAdmin(TimestampedAdmin):
    list_display = (
        "album",
        "disc_number",
        "track_number",
        "display_title",
        "recording",
        "duration_ms",
        "is_premium",
        "is_streamable",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "is_premium",
        "is_streamable",
        ("album", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "title_override",
        "album__title",
        "recording__work__title",
        "recording__work__composer__artist__name",
    )
    autocomplete_fields = ("album", "recording")
    actions = (make_published, make_draft, make_archived)
    ordering = ("album", "disc_number", "track_number", "sequence_order", "id")

    fieldsets = (
        (_("ارتباط‌ها"), {"fields": ("album", "recording")}),
        (_("نمایش/ترتیب"), {"fields": ("title_override", "disc_number", "track_number", "sequence_order")}),
        (_("فایل صوتی"), {
            "fields": (
                "audio_file",
                "file_size_bytes",
                "audio_bitrate_kbps",
                "audio_sample_rate_hz",
                "audio_codec",
                "duration_ms",
            )
        }),
        (_("دسترسی"), {"fields": ("is_premium", "is_streamable", "status")}),
        (_("سیستمی"), {"fields": ("created_at", "updated_at")}),
    )


# =========================================================
# Admin site cosmetics (optional)
# =========================================================
admin.site.site_header = _("مدیریت موسیقی کلاسیک")
admin.site.site_title = _("پنل ادمین")
admin.site.index_title = _("مدیریت محتوا")
