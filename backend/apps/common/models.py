from __future__ import annotations
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from uuid import uuid4
from django.db.models import Sum, Count
import os
from django.utils import timezone


# =========================================================
# Custom Manager for App MUSIC
# =========================================================
class AlbumQuerySet(models.QuerySet):
    def with_track_stats(self):
        return self.annotate(
            annotated_total_tracks=Count('tracks'),
            annotated_total_duration=Sum('tracks__duration_ms')
        )


class AlbumManager(models.Manager):
    def get_queryset(self):
        return AlbumQuerySet(self.model, using=self._db)

    def with_track_stats(self):
        return self.get_queryset().with_track_stats()


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
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    date_path = timezone.now().strftime("%Y/%m")

    # MEDIA_ROOT/protected/tracks/2026/06/a1b2c3d4e5f6.mp3
    return os.path.join("protected", "tracks", date_path, filename)
