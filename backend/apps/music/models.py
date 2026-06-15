from django.db import models
from django.core.validators import FileExtensionValidator
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from apps.common.models import (TimeStampedModel, ArchiveUploadStatus, PublishStatus,
    unique_slugify, artist_image_path , album_cover_path,
    track_cover_path ,track_audio_path, AlbumManager ,
    AlbumQuerySet , upload_path_handler )

from uuid import uuid4
from os import path
from mutagen import File as MutagenFile, MutagenError
import datetime
from re import search
from django.utils.text import slugify
from django.core.files.base import ContentFile
from logging import getLogger


logger = getLogger(__name__)


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


class Genre(TimeStampedModel):
    name = models.CharField(_("نام ژانر"), max_length=100, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, allow_unicode=True)

    class Meta:
        verbose_name = _("ژانر")
        verbose_name_plural = _("ژانرها")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Instrument(TimeStampedModel):
    name = models.CharField(_("نام ساز"), max_length=25, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=35, unique=True, allow_unicode=True)

    class Meta:
        verbose_name = _("ساز")
        verbose_name_plural = _("ساز ها")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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

    related_artists = models.ManyToManyField("self",blank=True,symmetrical=False)

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
    title = models.CharField(_("عنوان آلبوم"), max_length=300 , blank = True,default="untitled")
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, blank=True, allow_unicode=True)
    source_path = models.CharField(max_length=500, unique=True , null=True)
    cover_image = models.ImageField(_("تصویر آلبوم"),upload_to=album_cover_path,null=True,blank=True,validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    release_date = models.DateField(_("تاریخ انتشار"), null=True, blank=True)
    conductor = models.CharField(_("نام رهبر ارکستر"), max_length=255, blank=True)
    orchestra = models.CharField(_("نام ارکستر"), max_length=255, blank=True)
    soloist = models.CharField(_("نام نوازنده"), max_length=255, blank=True)
    ensemble = models.CharField(_("نام گروه موسیقی"), max_length=255, blank=True)
    status = models.CharField(_("وضعیت انتشار"),max_length=20,choices=PublishStatus.choices,default=PublishStatus.PUBLISHED,db_index=True)

    objects = AlbumManager()

    class Meta:
        verbose_name = _("آلبوم")
        verbose_name_plural = _("آلبوم‌ها")
        ordering = ["-release_date", "title"]
        indexes = [
            models.Index(fields=["release_date"]),
            models.Index(fields=["status"]),
        ]

    @property
    def total_tracks(self):
        if hasattr(self, 'annotated_total_tracks'):
            return self.annotated_total_tracks
        return self.tracks.count()

    @property
    def total_duration_ms(self):
        if hasattr(self, 'annotated_total_duration'):
            return self.annotated_total_duration or 0
        return self.tracks.aggregate(total=Sum("duration_ms"))["total"] or 0

    @property
    def on_this_album(self):
        names = [self.composer, self.conductor, self.orchestra, self.soloist, self.ensemble]
        return [name.strip() for name in names if name and name.strip()]

    def save(self, *args, **kwargs):
        if not self.slug:
            slug_source = self.title if self.title.strip() else f"untitled-{uuid4().hex[:8]}"
            self.slug = unique_slugify(self, "slug", slug_source)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title if self.title else _("بدون عنوان")



class AlbumArchiveUpload(TimeStampedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="archive_uploads")
    archive_file = models.FileField(upload_to="protected/tmp/archives/")
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
    zip_file = models.FileField(upload_to='protected/exports/albums/zips/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=ExportStatus.choices, default=ExportStatus.PENDING)
    error_log = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"ZIP Export for {self.album.title} - {self.status}"

# =========================================================
# Track Model
# =========================================================

class Track(TimeStampedModel):

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="tracks", null=True, blank=True, verbose_name=_("آلبوم"))
    title = models.CharField(_("عنوان ترک"), max_length=300 , blank=True, default="Untitled")
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, blank=True, allow_unicode=True)
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, related_name="tracks", verbose_name=_("ژانر"))
    audio_file = models.FileField(_("فایل صوتی"),upload_to=track_audio_path, validators=[FileExtensionValidator(["mp3", "wav", "flac"])],max_length=500)
    cover_image = models.ImageField(_("کاور اختصاصی ترک"), upload_to=track_cover_path, null=True, blank=True, help_text=_("اگر سینگل ترک است، حتماً کاور آپلود شود. در صورت داشتن آلبوم، کاور آلبوم اولویت دارد."))
    release_date = models.DateField(_("تاریخ انتشار ترک"), null=True, blank=True, help_text=_("مخصوص سینگل ترک‌ها"))
    composer = models.ForeignKey(Artist, on_delete=models.SET_NULL, null=True, blank=True, related_name="composed_tracks", verbose_name=_("آهنگساز"))
    singer = models.ForeignKey(Artist, on_delete=models.SET_NULL, null=True, blank=True, related_name="sung_tracks", verbose_name=_("خواننده"))
    duration_ms = models.PositiveIntegerField(_("مدت زمان (میلی‌ثانیه)"), null=True, blank=True)
    description = models.TextField(_("توضیحات"), blank=True)
    track_number = models.PositiveIntegerField(_("شماره ترک در آلبوم"), null=True, blank=True)
    status = models.CharField(_("وضعیت انتشار"), max_length=20, choices=PublishStatus.choices, default=PublishStatus.PUBLISHED, db_index=True)
    instrument = models.ForeignKey(Instrument,on_delete=models.SET_NULL,related_name="tracks",verbose_name=_("ساز"),null=True, blank=True)
    is_chosen = models.BooleanField(default=False, help_text=_("منتخب"))

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

    def extract_metadata(self):
        if not self.audio_file:
            return

        try:
            file_path = self.audio_file.path


            audio_easy = MutagenFile(file_path, easy=True)
            audio_raw = MutagenFile(file_path)

            if audio_easy is None or audio_raw is None:
                return

            if hasattr(audio_easy, 'info') and not self.duration_ms:
                self.duration_ms = int(getattr(audio_easy.info, 'length', 0) * 1000)

            def get_safe_string(tag_name, max_length=255):
                value = audio_easy.get(tag_name)
                if value and isinstance(value, list) and value[0]:
                    cleaned_value = str(value[0]).strip()
                    return cleaned_value[:max_length]
                return None

            if not self.title or self.title == "Untitled":
                extracted_title = get_safe_string('title')
                if extracted_title:
                    self.title = extracted_title

            tag_artist = get_safe_string('artist')
            if not self.singer and tag_artist:
                self.singer, _ = Artist.objects.get_or_create(name=tag_artist)

            tag_composer = get_safe_string('composer')
            if not self.composer and tag_composer:
                self.composer, _ = Artist.objects.get_or_create(name=tag_composer)

            tag_genre = get_safe_string('genre', max_length=100)

            if not self.genre and tag_genre:
                genre_slug = slugify(tag_genre.strip(), allow_unicode=True)
                self.genre = Genre.objects.filter(slug=genre_slug).first()


            if not self.track_number:
                tag_track = get_safe_string('tracknumber')
                if tag_track:
                    match = search(r'\d+', tag_track)
                    if match:
                        self.track_number = int(match.group())

            if not self.release_date:
                tag_date = get_safe_string('date')
                if tag_date:
                    year_match = search(r'(19|20)\d{2}', tag_date)
                    if year_match:
                        self.release_date = datetime.date(int(year_match.group()), 1, 1)


            if not self.cover_image:
                image_data = None
                mime_type = None

                if hasattr(audio_raw, 'tags') and audio_raw.tags:
                    for tag in audio_raw.tags.values():
                        if tag.__class__.__name__ == 'APIC':
                            image_data = tag.data
                            mime_type = tag.mime
                            break

                if not image_data and hasattr(audio_raw, 'pictures') and audio_raw.pictures:
                    pic = audio_raw.pictures[0]
                    image_data = pic.data
                    mime_type = pic.mime

                if image_data:
                    ext = 'jpg'
                    if mime_type == 'image/png':
                        ext = 'png'
                    elif mime_type in ['image/jpeg', 'image/jpg']:
                        ext = 'jpg'
                    elif mime_type == 'image/webp':
                        ext = 'webp'

                    filename = f"track_cover_{self.id or uuid4().hex[:8]}.{ext}"

                    self.cover_image.save(filename, ContentFile(image_data), save=False)

        except MutagenError as e:
            logger.warning(f"MutagenError extracting metadata for track {self.id}: {e}")
        except Exception as e:
            logger.error(f"General Error extracting metadata for track {self.id}: {e}", exc_info=True)

    @property
    def is_single(self):
        return self.album is None

    @property
    def effective_cover_image(self):
        if self.album and self.album.cover_image:
            return self.album.cover_image
        return self.cover_image

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        super().save(*args, **kwargs)

        if is_new and self.audio_file:
            from .tasks import extract_track_metadata_task
            from django.db import transaction

            transaction.on_commit(lambda: extract_track_metadata_task.delay(self.pk))

    def __str__(self):
        return f"{self.title} (Single)" if self.is_single else f"{self.title} - {self.album.title}"

