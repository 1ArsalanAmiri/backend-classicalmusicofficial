from django.db import models
from django.core.validators import FileExtensionValidator
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from apps.common.models import (TimeStampedModel, ArchiveUploadStatus, PublishStatus,
    unique_slugify, artist_image_path , album_cover_path,
    track_cover_path ,track_audio_path, AlbumManager)
from uuid import uuid4
from logging import getLogger
from django.conf import settings
from django.utils import timezone


logger = getLogger(__name__)


# Choices

class ArtistRole(models.TextChoices):
    # ==========================
    COMPOSER = "composer", _("آهنگساز")
    CONDUCTOR = "conductor", _("رهبر ارکستر")
    ORCHESTRA = "orchestra", _("ارکستر")
    SOLOIST = "soloist", _("سولیست")
    ENSEMBLE = "ensemble", _("گروه موسیقی")
    SINGER = "singer", _("خواننده")

    # سازها
    PIANIST = "pianist", _("پیانو")
    ORGANIST = "organist", _("ارگ")
    HARPSICHORDIST = "harpsichordist", _("هارپسیکورد")
    CELLIST = "cellist", _("ویولنسل")
    VIOLINIST = "violinist", _("ویولن")
    VIOLIST = "violist", _("ویولا")
    VIOLA_DA_GAMBA = "viola_da_gamba", _("ویولا دا گامبا")
    GUITARIST = "guitarist", _("گیتار")
    LUTENIST = "lutenist", _("لوت")
    DOUBLE_BASSIST = "double_bassist", _("کنتر باس")
    HARPIST = "harpist", _("هارپ")
    TRUMPETER = "trumpeter", _("ترومپت")
    HORN = "horn", _("کُر")
    TROMBONIST = "trombonist", _("ترومبون")
    TUBA = "tuba", _("توبا")
    CLARINETIST = "clarinetist", _("کلارینت")
    OBOIST = "oboist", _("اُبوا")
    FLUTIST = "flutist", _("فلوت")
    BASSOONIST = "bassoonist", _("فاگوت (باسون)")
    RECORDER = "recorder", _("فلوت ریکوردر")
    SAXOPHONIST = "saxophonist", _("ساکسیفون")
    ACCORDIONIST = "accordionist", _("آکوردئون")
    PERCUSSIONIST = "percussionist", _("پرکاشن")

    # وکال
    SOPRANO = "soprano", _("سوپرانو")
    MEZZO_SOPRANO = "mezzo_soprano", _("متزو سوپرانو")
    COUNTERTENOR = "countertenor", _("کانتر تنور")
    TENOR = "tenor", _("تنور")
    BASS_BARITONE = "bass_baritone", _("باس باریتون")

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


# Artist & Label Model

class Label(TimeStampedModel):
    name = models.CharField(_("نام لیبل"), max_length=255, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, allow_unicode=True)
    logo = models.ImageField(
        _("لوگوی لیبل"),
        upload_to="labels/logos/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])]
    )
    country = models.CharField(_("کشور"), max_length=100, blank=True)
    website = models.URLField(_("وب‌سایت"), max_length=200, blank=True)
    description = models.TextField(_("توضیحات"), blank=True)

    likes_count = models.PositiveIntegerField(_("تعداد لایک"), default=0)
    followers_count = models.PositiveIntegerField(_("تعداد فالوور"), default=0)


    class Meta:
        verbose_name = _("لیبل (ناشر)")
        verbose_name_plural = _("لیبل‌ها")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Album(TimeStampedModel):
    main_artists = models.ManyToManyField('Artist',blank=True,verbose_name=_("آرتیست‌های اصلی"),related_name="main_albums")
    title = models.CharField(_("عنوان آلبوم"), max_length=300, blank=True, default="untitled")
    title_fa = models.CharField(_("عنوان فارسی"), max_length=300, blank=True, null=True)
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, blank=True, allow_unicode=True)
    source_path = models.CharField(max_length=500, unique=True, blank=True, null=True)
    cover_image = models.ImageField(_("تصویر آلبوم"), upload_to=album_cover_path, null=True, blank=True,validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    release_year = models.PositiveIntegerField(_("سال انتشار"), null=True, blank=True)
    description = models.TextField(_("توضیحات نهایی آلبوم"), blank=True)
    status = models.CharField(_("وضعیت انتشار"), max_length=20, choices=PublishStatus.choices,default=PublishStatus.PUBLISHED, db_index=True)
    label = models.ForeignKey(Label, on_delete=models.SET_NULL, null=True, blank=True, related_name="albums_by_label",verbose_name=_("لیبل ناشر"))
    likes_count = models.PositiveIntegerField(_("تعداد لایک"), default=0)
    comments_count = models.PositiveIntegerField(_("تعداد کامنت"), default=0)
    objects = AlbumManager()

    class Meta:
        verbose_name = _("آلبوم")
        verbose_name_plural = _("آلبوم‌ها")
        ordering = ["-release_year", "title"]
        indexes = [
            models.Index(fields=["release_year"]),
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
        return Artist.objects.filter(album_credits__album=self).distinct()

    def __str__(self):
        return self.title if self.title else _("بدون عنوان")


class Artist(TimeStampedModel):
    name = models.CharField(_("نام آرتیست"), max_length=255)
    nickname = models.CharField(_("نام مستعار"), max_length=255, blank=True, null=True, help_text=_("در صورت نداشتن نام مستعار، خالی بگذارید"))
    slug = models.SlugField(_("اسلاگ"), max_length=120, unique=True, blank=True, allow_unicode=True)
    country = models.CharField(_("ملیت/کشور"), max_length=100, blank=True)
    artist_type = models.CharField(_("نوع آرتیست"),max_length=20,choices=ArtistRole.choices,default=ArtistRole.OTHER,db_index=True)
    related_artists = models.ManyToManyField("self",blank=True,symmetrical=False)
    era = models.CharField(_("دوره زمانی"),max_length=20,choices=EraChoices.choices,null=True,blank=True,db_index=True)
    image = models.ImageField(_("عکس"),upload_to=artist_image_path,null=True,blank=True,validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    biography = models.TextField(_("بیوگرافی"), blank=True)

    birth_year = models.PositiveIntegerField(_("سال تولد"), null=True, blank=True, help_text=_("مثال:1958"))
    death_year = models.PositiveIntegerField(_("سال فوت"), null=True, blank=True, help_text=_("اگر زنده هستش ، این فیلد رو خالی بگذارید"))

    likes_count = models.PositiveIntegerField(_("تعداد لایک"), default=0)
    followers_count = models.PositiveIntegerField(_("تعداد فالوور"), default=0)



    class Meta:
        verbose_name = _("آرتیست")
        verbose_name_plural = _("آرتیست‌ها")
        ordering = ["name"]

    @property
    def all_related_tracks(self):
        return self.participated_tracks.all()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_artist_type_display()})"


class AlbumCredit(TimeStampedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="credits", verbose_name=_("آلبوم"))
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="album_credits", verbose_name=_("آرتیست"))
    role = models.CharField(_("نقش"), max_length=50, choices=ArtistRole.choices)

    class Meta:
        verbose_name = _("عوامل آلبوم")
        verbose_name_plural = _("عوامل آلبوم")
        unique_together = ('album', 'artist', 'role')

    def __str__(self):
        return f"{self.artist.name} - {self.get_role_display()} in {self.album.title}"


# Album Model

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


class AlbumZipExport(models.Model):
    album = models.ForeignKey('Album', on_delete=models.CASCADE, related_name='zip_exports')
    zip_file = models.FileField(upload_to='album_zips/', blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        try:
            return f"{self.album.slug} - {self.status}"
        except Album.DoesNotExist:
            return f"(آلبوم حذف شده) - {self.status}"

# Track Model

class Track(TimeStampedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="tracks", null=True, blank=True,verbose_name=_("آلبوم"))
    title = models.CharField(_("عنوان ترک"), max_length=300, blank=True, default="Untitled")
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, blank=True, allow_unicode=True)
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, related_name="tracks",verbose_name=_("ژانر"))
    audio_file = models.FileField(_("فایل صوتی"), upload_to=track_audio_path,validators=[FileExtensionValidator(["mp3", "wav", "flac"])], max_length=500)
    cover_image = models.ImageField(_("کاور اختصاصی ترک"), upload_to=track_cover_path, null=True, blank=True)
    release_date = models.DateField(_("تاریخ انتشار ترک"), null=True, blank=True)
    artists = models.ManyToManyField(Artist, related_name="participated_tracks", blank=True,verbose_name=_("آرتیست‌های مشارکت‌کننده"))
    duration_ms = models.PositiveIntegerField(_("مدت زمان (میلی‌ثانیه)"), null=True, blank=True)
    description = models.TextField(_("توضیحات"), blank=True)
    track_number = models.PositiveIntegerField(_("شماره ترک در آلبوم"), null=True, blank=True)
    status = models.CharField(_("وضعیت انتشار"), max_length=20, choices=PublishStatus.choices,default=PublishStatus.PUBLISHED, db_index=True)
    instrument = models.ForeignKey(Instrument, on_delete=models.SET_NULL, related_name="tracks", verbose_name=_("ساز"),null=True, blank=True)
    is_chosen = models.BooleanField(default=False)
    label = models.ForeignKey(Label, on_delete=models.SET_NULL, null=True, blank=True, related_name="tracks",verbose_name=_("لیبل ناشر"))
    likes_count = models.PositiveIntegerField(_("تعداد لایک"), default=0)
    play_count = models.PositiveBigIntegerField(_("تعداد کل پخش"), default=0)


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
        return self.album_id is None

    @property
    def effective_cover_image(self):
        try:
            if self.album_id and self.album.cover_image:
                return self.album.cover_image
        except Album.DoesNotExist:
            pass
        return self.cover_image

    def save(self, *args, **kwargs):
        if not self.slug:
            slug_source = self.title if self.title and self.title.strip() else f"track-{uuid4().hex[:8]}"
            self.slug = unique_slugify(self, "slug", slug_source)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.is_single:
            return f"{self.title} (Single)"
        try:
            return f"{self.title} - {self.album.title}"
        except Album.DoesNotExist:
            return f"{self.title} - (آلبوم نامشخص یا حذف شده)"



class PlayHistory(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="play_history",
        verbose_name=_("کاربر")
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="play_history",
        verbose_name=_("ترک")
    )
    last_played_at = models.DateTimeField(_("آخرین زمان پخش"), default=timezone.now)
    play_count = models.PositiveIntegerField(_("تعداد پخش کاربر"), default=1)

    class Meta:
        verbose_name = _("تاریخچه پخش")
        verbose_name_plural = _("تاریخچه پخش‌ها")
        unique_together = ('user', 'track')
        ordering = ['-last_played_at']
        indexes = [
            models.Index(fields=['user', '-last_played_at']),
        ]

    def __str__(self):
        return f"{self.user} listened to {self.track}"