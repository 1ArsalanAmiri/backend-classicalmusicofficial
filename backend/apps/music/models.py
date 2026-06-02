from __future__ import annotations
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _



# =========================================================
# Base
# =========================================================

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

    base_slug = slugify(value) or "item"
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


# =========================================================
# Taxonomies
# =========================================================

class Genre(TimeStampedModel):
    name = models.CharField(_("نام"), max_length=100, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, blank=True)
    description = models.TextField(_("توضیحات"), blank=True)

    class Meta:
        verbose_name = _("ژانر")
        verbose_name_plural = _("ژانرها")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Era(TimeStampedModel):
    name = models.CharField(_("نام"), max_length=100, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, blank=True)
    description = models.TextField(_("توضیحات"), blank=True)

    class Meta:
        verbose_name = _("دوره")
        verbose_name_plural = _("دوره‌ها")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class WorkType(TimeStampedModel):
    name = models.CharField(_("نام"), max_length=100, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, blank=True)

    class Meta:
        verbose_name = _("نوع اثر")
        verbose_name_plural = _("انواع اثر")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Label(TimeStampedModel):
    name = models.CharField(_("نام"), max_length=150, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=180, unique=True, blank=True)
    website = models.URLField(_("وب‌سایت"), blank=True)

    class Meta:
        verbose_name = _("لیبل")
        verbose_name_plural = _("لیبل‌ها")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =========================================================
# Artists / composers
# =========================================================

class ArtistType(models.TextChoices):
    PERSON = "person", _("شخص")
    ORCHESTRA = "orchestra", _("ارکستر")
    ENSEMBLE = "ensemble", _("گروه")
    CHOIR = "choir", _("کر")
    OTHER = "other", _("سایر")


class Artist(TimeStampedModel):
    name = models.CharField(_("نام"), max_length=255)
    sort_name = models.CharField(_("نام مرتب‌سازی"), max_length=255, blank=True, db_index=True)
    slug = models.SlugField(_("اسلاگ"), max_length=280, unique=True, blank=True)

    artist_type = models.CharField(
        _("نوع آرتیست"),
        max_length=20,
        choices=ArtistType.choices,
        default=ArtistType.PERSON,
        db_index=True,
    )
    country = models.CharField(_("کشور"), max_length=100, blank=True)
    birth_date = models.DateField(_("تاریخ تولد"), null=True, blank=True)
    death_date = models.DateField(_("تاریخ وفات"), null=True, blank=True)
    short_bio = models.TextField(_("بیو کوتاه"), blank=True)

    image = models.ImageField(
        _("تصویر"),
        upload_to="music/artists/images/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )

    is_active = models.BooleanField(_("فعال"), default=True, db_index=True)
    is_featured = models.BooleanField(_("ویژه"), default=False, db_index=True)
    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )

    genres = models.ManyToManyField(
        Genre,
        verbose_name=_("ژانرها"),
        related_name="artists",
        blank=True,
    )

    class Meta:
        verbose_name = _("آرتیست")
        verbose_name_plural = _("آرتیست‌ها")
        ordering = ["sort_name", "name"]

    def clean(self):
        if self.birth_date and self.death_date and self.death_date < self.birth_date:
            raise ValidationError({"death_date": _("تاریخ وفات نمی‌تواند قبل از تاریخ تولد باشد.")})

    def save(self, *args, **kwargs):
        if not self.sort_name:
            self.sort_name = self.name
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Composer(TimeStampedModel):
    artist = models.OneToOneField(
        Artist,
        verbose_name=_("آرتیست"),
        on_delete=models.CASCADE,
        related_name="composer_profile",
    )
    era = models.ForeignKey(
        Era,
        verbose_name=_("دوره"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="composers",
    )
    is_featured = models.BooleanField(_("ویژه"), default=False, db_index=True)

    class Meta:
        verbose_name = _("آهنگساز")
        verbose_name_plural = _("آهنگسازان")
        ordering = ["artist__sort_name", "artist__name"]

    def clean(self):
        if self.artist and self.artist.artist_type != ArtistType.PERSON:
            raise ValidationError({"artist": _("آهنگساز باید از نوع شخص باشد.")})

    def __str__(self):
        return self.artist.name


# =========================================================
# Works
# =========================================================

class Work(TimeStampedModel):
    composer = models.ForeignKey(Composer, verbose_name=_("آهنگساز"), on_delete=models.PROTECT, related_name="works")
    title = models.CharField(_("عنوان"), max_length=300)
    full_title = models.CharField(_("عنوان کامل"), max_length=500, blank=True)
    normalized_title = models.CharField(_("عنوان نرمال"), max_length=500, blank=True, db_index=True)
    slug = models.SlugField(_("اسلاگ"), max_length=550, unique=True, blank=True)

    genre = models.ForeignKey(Genre, verbose_name=_("ژانر"), on_delete=models.SET_NULL, null=True, blank=True, related_name="works")
    work_type = models.ForeignKey(WorkType, verbose_name=_("نوع اثر"), on_delete=models.SET_NULL, null=True, blank=True, related_name="works")
    era = models.ForeignKey(Era, verbose_name=_("دوره"), on_delete=models.SET_NULL, null=True, blank=True, related_name="works")

    composition_year = models.PositiveIntegerField(
        _("سال ساخت"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3000)],
    )

    parent_work = models.ForeignKey(
        "self",
        verbose_name=_("اثر والد"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_works",
    )

    description = models.TextField(_("توضیحات"), blank=True)
    is_featured = models.BooleanField(_("ویژه"), default=False, db_index=True)
    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )

    class Meta:
        verbose_name = _("اثر")
        verbose_name_plural = _("آثار")
        ordering = ["composer__artist__sort_name", "title"]
        constraints = [
            models.UniqueConstraint(fields=["composer", "title"], name="uniq_work_title_per_composer"),
        ]

    def clean(self):
        if self.parent_work_id and self.parent_work_id == self.id:
            raise ValidationError({"parent_work": _("اثر والد نمی‌تواند خود اثر باشد.")})

    def save(self, *args, **kwargs):
        if not self.full_title:
            self.full_title = self.title
        self.normalized_title = self.full_title.lower().strip()
        if not self.slug:
            self.slug = unique_slugify(self, "slug", f"{self.composer.artist.name}-{self.title}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.composer.artist.name} - {self.title}"


class WorkCatalogRef(TimeStampedModel):
    work = models.ForeignKey(Work, verbose_name=_("اثر"), on_delete=models.CASCADE, related_name="catalog_refs")
    number = models.CharField(_("شماره"), max_length=100)

    class Meta:
        verbose_name = _("مرجع کاتالوگ اثر")
        verbose_name_plural = _("مراجع کاتالوگ اثر")
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["work", "number"], name="uniq_work_catalog_ref"),
        ]

    def __str__(self):
        return f"{self.work.title} - {self.number}"


# =========================================================
# Recordings
# =========================================================

class RecordingType(models.TextChoices):
    STUDIO = "studio", _("استودیویی")
    LIVE = "live", _("اجرای زنده")
    OTHER = "other", _("سایر")


class CreditRole(models.TextChoices):
    COMPOSER = "composer", _("آهنگساز")
    CONDUCTOR = "conductor", _("رهبر ارکستر")
    SOLOIST = "soloist", _("سولیست")
    ORCHESTRA = "orchestra", _("ارکستر")
    ENSEMBLE = "ensemble", _("گروه")
    CHOIR = "choir", _("کر")
    PERFORMER = "performer", _("اجراکننده")
    ARRANGER = "arranger", _("تنظیم‌کننده")
    PRODUCER = "producer", _("تهیه‌کننده")


class Recording(TimeStampedModel):
    work = models.ForeignKey(Work, verbose_name=_("اثر"), on_delete=models.PROTECT, related_name="recordings")
    title_override = models.CharField(_("عنوان جایگزین"), max_length=300, blank=True)

    recording_type = models.CharField(
        _("نوع ضبط"),
        max_length=20,
        choices=RecordingType.choices,
        default=RecordingType.STUDIO,
        db_index=True,
    )
    recording_date = models.DateField(_("تاریخ ضبط"), null=True, blank=True)
    release_date = models.DateField(_("تاریخ انتشار"), null=True, blank=True)

    label = models.ForeignKey(
        Label,
        verbose_name=_("لیبل"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )

    is_complete_work = models.BooleanField(_("اجرای کامل اثر"), default=True, db_index=True)
    duration_ms = models.PositiveIntegerField(_("مدت زمان (ms)"), default=0)
    is_featured = models.BooleanField(_("ویژه"), default=False, db_index=True)
    popularity = models.FloatField(_("محبوبیت"), default=0.0, validators=[MinValueValidator(0.0)])
    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )

    class Meta:
        verbose_name = _("ضبط")
        verbose_name_plural = _("ضبط‌ها")
        ordering = ["-is_featured", "-release_date", "id"]

    @property
    def display_title(self):
        return self.title_override or self.work.full_title or self.work.title

    def __str__(self):
        return self.display_title


class RecordingCredit(TimeStampedModel):
    recording = models.ForeignKey(Recording, verbose_name=_("ضبط"), on_delete=models.CASCADE, related_name="credits")
    artist = models.ForeignKey(Artist, verbose_name=_("آرتیست"), on_delete=models.CASCADE, related_name="recording_credits")
    role = models.CharField(_("نقش"), max_length=20, choices=CreditRole.choices, db_index=True)
    credit_order = models.PositiveIntegerField(_("ترتیب"), default=0, db_index=True)
    is_primary = models.BooleanField(_("اصلی"), default=False, db_index=True)

    class Meta:
        verbose_name = _("کردیت ضبط")
        verbose_name_plural = _("کردیت‌های ضبط")
        ordering = ["recording", "credit_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recording", "artist", "role"],
                name="uniq_recording_artist_role",
            ),
        ]

    def clean(self):
        if self.role == CreditRole.COMPOSER and not hasattr(self.artist, "composer_profile"):
            raise ValidationError({"artist": _("برای نقش آهنگساز، آرتیست باید پروفایل آهنگساز داشته باشد.")})

    def __str__(self):
        return f"{self.recording} - {self.artist.name} ({self.role})"


# =========================================================
# Albums / tracks
# =========================================================

class AlbumType(models.TextChoices):
    ALBUM = "album", _("آلبوم")
    SINGLE = "single", _("تک‌آهنگ")
    EP = "ep", _("ای‌پی")
    COMPILATION = "compilation", _("منتخب")
    BOX_SET = "box_set", _("باکس ست")


class Album(TimeStampedModel):
    title = models.CharField(_("عنوان"), max_length=300)
    slug = models.SlugField(_("اسلاگ"), max_length=350, unique=True, blank=True)

    album_type = models.CharField(
        _("نوع آلبوم"),
        max_length=20,
        choices=AlbumType.choices,
        default=AlbumType.ALBUM,
        db_index=True,
    )
    label = models.ForeignKey(Label, verbose_name=_("لیبل"), on_delete=models.SET_NULL, null=True, blank=True, related_name="albums")
    release_date = models.DateField(_("تاریخ انتشار"), null=True, blank=True)

    cover_image = models.ImageField(
        _("کاور"),
        upload_to="music/albums/covers/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )

    description = models.TextField(_("توضیحات"), blank=True)
    editorial_note = models.TextField(_("یادداشت تحریریه"), blank=True)

    is_featured = models.BooleanField(_("ویژه"), default=False, db_index=True)
    popularity = models.FloatField(_("محبوبیت"), default=0.0, validators=[MinValueValidator(0.0)])
    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )

    class Meta:
        verbose_name = _("آلبوم")
        verbose_name_plural = _("آلبوم‌ها")
        ordering = ["-release_date", "title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Track(TimeStampedModel):
    album = models.ForeignKey(Album, verbose_name=_("آلبوم"), on_delete=models.PROTECT, related_name="tracks")
    recording = models.ForeignKey(Recording, verbose_name=_("ضبط"), on_delete=models.PROTECT, related_name="tracks")

    title_override = models.CharField(_("عنوان جایگزین"), max_length=300, blank=True)
    disc_number = models.PositiveIntegerField(_("شماره دیسک"), default=1, validators=[MinValueValidator(1)])
    track_number = models.PositiveIntegerField(_("شماره ترک"), default=1, validators=[MinValueValidator(1)])
    sequence_order = models.PositiveIntegerField(_("ترتیب کلی"), default=0, db_index=True)
    duration_ms = models.PositiveIntegerField(_("مدت زمان (ms)"), default=0)

    audio_file = models.FileField(
        _("فایل صوتی"),
        upload_to="music/tracks/audio/",
        validators=[FileExtensionValidator(["mp3", "m4a", "aac", "flac", "wav", "ogg"])],
    )
    file_size_bytes = models.BigIntegerField(_("حجم فایل"), default=0)
    audio_bitrate_kbps = models.PositiveIntegerField(_("بیت‌ریت"), null=True, blank=True)
    audio_sample_rate_hz = models.PositiveIntegerField(_("نرخ نمونه‌برداری"), null=True, blank=True)
    audio_codec = models.CharField(_("کدک"), max_length=30, blank=True)

    is_premium = models.BooleanField(_("پریمیوم"), default=False, db_index=True)
    is_streamable = models.BooleanField(_("قابل پخش"), default=True, db_index=True)
    status = models.CharField(
        _("وضعیت انتشار"),
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )

    class Meta:
        verbose_name = _("ترک")
        verbose_name_plural = _("ترک‌ها")
        ordering = ["album", "disc_number", "track_number", "sequence_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["album", "disc_number", "track_number"],
                name="uniq_album_disc_track_number",
            ),
        ]

    @property
    def display_title(self):
        return self.title_override or self.recording.display_title

    def __str__(self):
        return f"{self.album.title} - {self.disc_number}.{self.track_number} - {self.display_title}"
