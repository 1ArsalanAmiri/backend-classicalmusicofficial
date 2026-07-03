from uuid import uuid4
from django.core.validators import FileExtensionValidator
from django.db import models
from apps.common.models import TimeStampedModel, PublishStatus, unique_slugify
from django.utils.translation import gettext_lazy as _
from apps.music.models import Artist, EraChoices
from django.conf import settings
from django.db import models




class Video(TimeStampedModel):
    title = models.CharField(_("عنوان ویدیو"), max_length=300)
    slug = models.SlugField(_("اسلاگ"), max_length=300, unique=True, blank=True, allow_unicode=True)

    artists = models.ManyToManyField(
        Artist,
        related_name="videos",
        blank=True,
        verbose_name=_("آرتیست‌های ویدیو")
    )

    era = models.CharField(
        _("دوره زمانی"),
        max_length=20,
        choices=EraChoices.choices,
        null=True,
        blank=True,
        db_index=True
    )

    recording_year = models.PositiveIntegerField(_("سال ضبط"), null=True, blank=True , help_text=_("مثال:2018"))
    duration_seconds = models.PositiveIntegerField(_("مدت زمان (ثانیه)"), null=True, blank=True)

    cover_image = models.ImageField(
        _("کاور ویدیو"),
        upload_to="videos/covers/",
        null=True,
        blank=True
    )

    video_file = models.FileField(
        upload_to='videos/raw/',
        verbose_name='فایل خام ویدیو',
        null=True,
        blank=True
    )

    hls_file = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text='مسیر فایل master.m3u8 که به صورت خودکار توسط سیستم پر می‌شود',
        verbose_name='مسیر استریم HLS'
    )

    status = models.CharField(
        max_length=20,
        choices=[('processing', 'در حال پردازش'), ('published', 'منتشر شده')],
        default='processing'
    )

    view_count = models.PositiveBigIntegerField(_("بازدید"), default=0)
    likes_count = models.PositiveIntegerField(_("لایک ها"), default=0)

    class Meta:
        verbose_name = _("ویدیو")
        verbose_name_plural = _("ویدیوها")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recording_year"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            slug_source = self.title if self.title and self.title.strip() else f"video-{uuid4().hex[:8]}"
            self.slug = unique_slugify(self, "slug", slug_source)
        super().save(*args, **kwargs)
    def __str__(self):
        return self.title


class VideoHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_histories',
        verbose_name='کاربر'
    )
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='histories',
        verbose_name='ویدیو'
    )
    watched_seconds = models.PositiveIntegerField(
        default=0,
        help_text='ثانیه‌ای که کاربر تماشا را متوقف کرده است.',
        verbose_name='ثانیه‌های تماشاشده'
    )
    is_completed = models.BooleanField(
        default=False,
        help_text='آیا کاربر ویدیو را تا انتها دیده است؟',
        verbose_name='تکمیل شده'
    )
    last_watched_at = models.DateTimeField(
        auto_now=True,
        verbose_name='آخرین زمان تماشا'
    )

    class Meta:
        verbose_name = 'تاریخچه تماشای ویدیو'
        verbose_name_plural = 'تاریخچه تماشای ویدیوها'
        unique_together = ('user', 'video')
        indexes = [
            models.Index(fields=['user', 'video']),
            models.Index(fields=['-last_watched_at']),
        ]

    def __str__(self):
        return f"{self.user} - {self.video.title} ({self.watched_seconds}s)"
