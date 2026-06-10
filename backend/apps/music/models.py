from __future__ import annotations
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Sum
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from uuid import uuid4


# =========================================================
# Utilities & Base Models
# =========================================================
class ArchiveUploadStatus(models.TextChoices):
    PENDING = "pending", _("در صف انتظار")
    EXTRACTING = "extracting", _("در حال استخراج")
    PROCESSING = "processing", _("در حال پردازش متادیتا و آپلود")
    COMPLETED = "completed", _("تکمیل شده")
    FAILED = "failed", _("خطا")


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True, db_index=True)

    class Meta:
        abstract = True


class PublishStatus(models.TextChoices):
    DRAFT = "draft", _("پیش‌نویس")
    PUBLISHED = "published", _("منتشرشده")
    ARCHIVED = "archived", _("آرشیوشده")


def unique_slugify(instance, slug_field_name: str, value: str):
    slug_field = instance._meta.get_field(slug_field_name)
    max_length = slug_field.max_length
    base_slug = slugify(value, allow_unicode=True) or "item"
    base_slug = base_slug[:max_length]

    slug = base_slug
    model_class = instance.__class__
    counter = 2

    qs = model_class._default_manager.all()
    if instance.pk:
        qs = qs.exclude(pk=instance.pk)

    while qs.filter(**{slug_field_name: slug}).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:max_length - len(suffix)]}{suffix}"
        counter += 1

    return slug


def upload_path_handler(instance, filename, folder_name):
    ext = filename.split('.')[-1]
    return f"music/{folder_name}/{instance.id or uuid4().hex[:8]}/{uuid4().hex}.{ext}"


def artist_image_path(instance, filename):
    return upload_path_handler(instance, filename, "artists/images")


def album_cover_path(instance, filename):
    return upload_path_handler(instance, filename, "albums/covers")


def track_cover_path(instance, filename):
    return upload_path_handler(instance, filename, "tracks/covers")


def track_audio_path(instance, filename):
    return upload_path_handler(instance, filename, "tracks/audio")


# =========================================================
# Choices
# =========================================================

class ArtistType(models.TextChoices):
    PERSON = "person", _("شخص")
    ORCHESTRA = "orchestra", _("ارکستر")
    ENSEMBLE = "ensemble", _("گروه")
    CHOIR = "choir", _("کر")
    OTHER = "other", _("سایر")


class EraChoices(models.TextChoices):
    RENAISSANCE = "renaissance", _("رنسانس")
    BAROQUE = "baroque", _("باروک")
    CLASSICAL = "classical", _("کلاسیک")
    ROMANTIC = "romantic", _("رمانتیک")
    IMPRESSIONISM = "impressionism", _("امپرسیونیسم")
    MODERN = "modern", _("مدرن")
    CONTEMPORARY = "contemporary", _("معاصر")


# =========================================================
# Artist Model
# =========================================================

class Artist(TimeStampedModel):
    name = models.CharField(_("نام آرتیست"), max_length=255)
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, blank=True, allow_unicode=True)
    country = models.CharField(_("ملیت/کشور"), max_length=100, blank=True)

    artist_type = models.CharField(
        _("نوع آرتیست"),
        max_length=20,
        choices=ArtistType.choices,
        default=ArtistType.PERSON,
        db_index=True
    )

    era = models.CharField(
        _("دوره زمانی"),
        max_length=20,
        choices=EraChoices.choices,
        null=True,
        blank=True,
        db_index=True
    )

    image = models.ImageField(
        _("عکس"),
        upload_to=artist_image_path,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])]
    )

    biography = models.TextField(_("بیوگرافی"), blank=True)


    class Meta:
        verbose_name = _("آرتیست")
        verbose_name_plural = _("آرتیست‌ها")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_artist_type_display()})"

# =========================================================
# Album Model
# =========================================================

class Album(TimeStampedModel):
    composer = models.CharField(_("نام آهنگساز"), max_length=255, blank=True)
    title = models.CharField(_("عنوان آلبوم"), max_length=300 , blank = True , null=True)
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, blank=True, allow_unicode=True)
    source_path = models.CharField(max_length=500, unique=True , null=True)

    cover_image = models.ImageField(
        _("تصویر آلبوم"),
        upload_to=album_cover_path,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])]
    )

    release_date = models.DateField(_("تاریخ انتشار"), null=True, blank=True)

    conductor = models.CharField(_("نام رهبر ارکستر"), max_length=255, blank=True)
    orchestra = models.CharField(_("نام ارکستر"), max_length=255, blank=True)
    soloist = models.CharField(_("نام نوازنده"), max_length=255, blank=True)
    ensemble = models.CharField(_("نام گروه موسیقی"), max_length=255, blank=True)


    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.PUBLISHED,
        db_index=True
    )

    class Meta:
        verbose_name = _("آلبوم")
        verbose_name_plural = _("آلبوم‌ها")
        ordering = ["-release_date", "title"]
        indexes = [
            models.Index(fields=["release_date"]),
        ]

    @property
    def total_tracks(self):
        return self.tracks.count()

    @property
    def total_duration_ms(self):
        return self.tracks.aggregate(total=Sum("duration_ms"))["total"] or 0

    @property
    def on_this_album(self):
        names = [self.composer, self.conductor, self.orchestra, self.soloist, self.ensemble]
        return [name.strip() for name in names if name and name.strip()]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or "بدون عنوان"



class AlbumArchiveUpload(TimeStampedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="archive_uploads")
    archive_file = models.FileField(upload_to="tmp/archives/")
    task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=ArchiveUploadStatus.choices, default=ArchiveUploadStatus.PENDING)
    progress = models.PositiveIntegerField(default=0, help_text=_("درصد پیشرفت از $0$ تا $100$"))
    error_log = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _("آپلود گروهی آلبوم")
        verbose_name_plural = _("آپلودهای گروهی آلبوم")



class AlbumZipExport(TimeStampedModel):
    class ExportStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')

    album = models.OneToOneField('Album', on_delete=models.CASCADE, related_name='zip_export')
    zip_file = models.FileField(upload_to='exports/albums/zips/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=ExportStatus.choices, default=ExportStatus.PENDING)
    error_log = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"ZIP Export for {self.album.title} - {self.status}"

# =========================================================
# Track Model
# =========================================================

class Track(TimeStampedModel):

    album = models.ForeignKey(Album,on_delete=models.CASCADE,related_name="tracks",null=True,blank=True,verbose_name=_("آلبوم"))

    title = models.CharField(_("عنوان ترک"), max_length=300)
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, blank=True, allow_unicode=True)
    genre = models.CharField(_("زانر"), max_length=30)

    audio_file = models.FileField(
        _("فایل صوتی"),
        upload_to=track_audio_path,
        validators=[FileExtensionValidator(["mp3", "wav", "flac"])]
    )
    cover_image = models.ImageField(
        _("کاور اختصاصی ترک"),
        upload_to=track_cover_path,
        null=True,
        blank=True,
        help_text=_("اگر سینگل ترک است، حتماً کاور آپلود شود. در صورت داشتن آلبوم، کاور آلبوم اولویت دارد.")
    )

    release_date = models.DateField(_("تاریخ انتشار ترک"), null=True, blank=True, help_text=_("مخصوص سینگل ترک‌ها"))

    composer = models.ForeignKey(Artist, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="composed_tracks", verbose_name=_("آهنگساز"))
    singer = models.ForeignKey(Artist, on_delete=models.SET_NULL, null=True, blank=True, related_name="sung_tracks",
                               verbose_name=_("خواننده"))

    duration_ms = models.PositiveIntegerField(_("مدت زمان (میلی‌ثانیه)"), null=True, blank=True)
    description = models.TextField(_("توضیحات"), blank=True)

    track_number = models.PositiveIntegerField(_("شماره ترک در آلبوم"), null=True, blank=True)

    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.PUBLISHED,
        db_index=True
    )
    instrument = models.CharField(verbose_name=_("ساز"), max_length=20, null=True, blank=True)

    class Meta:
        verbose_name = _("ترک")
        verbose_name_plural = _("ترک‌ها")
        ordering = ["album", "track_number"]
        constraints = [
            models.UniqueConstraint(
                fields=['album', 'track_number'],
                name='uniq_track_position_in_album',
                condition=models.Q(album__isnull=False) & models.Q(track_number__isnull=False)
            )
        ]

    @property
    def is_single(self):
        return self.album is None

    @property
    def effective_cover_image(self):

        if self.album and self.album.cover_image:
            return self.album.cover_image
        return self.cover_image


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.title)

        if self.album and self.album.cover_image and not self.cover_image:
            self.cover_image = self.album.cover_image
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.title} (Single)" if self.is_single else f"{self.title} - {self.album.title}"


