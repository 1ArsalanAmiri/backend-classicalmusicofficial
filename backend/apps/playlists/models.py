from django.db import models
from apps.common.models import TimeStampedModel, unique_slugify
from apps.music.models import Track
from django.utils.translation import gettext_lazy as _
from django.conf import settings


def playlist_cover_path(instance, filename):
    return f"playlists/{instance.slug}/{filename}"


class Playlist(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
        verbose_name=_("کاربر")
    )
    title = models.CharField(_("عنوان پلی‌لیست"), max_length=255)
    title_fa = models.CharField(_("عنوان فارسی"), max_length=255, blank=True)
    slug = models.SlugField(_("اسلاگ"), max_length=280, unique=True, blank=True, allow_unicode=True)
    description = models.TextField(_("توضیحات"), blank=True)
    cover_image = models.ImageField(
        _("تصویر کاور"),
        upload_to="playlists/covers/",
        null=True, blank=True
    )
    tracks = models.ManyToManyField(
        Track,
        through='PlaylistItem',
        related_name='in_playlists',
        verbose_name=_("ترک‌ها")
    )

    class Meta:
        verbose_name = _("پلی‌لیست")
        verbose_name_plural = _("پلی‌لیست‌ها")
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_str = f"{self.title}-{self.user_id}"
            self.slug = unique_slugify(self, "slug", base_str)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class PlaylistItem(TimeStampedModel):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("پلی‌لیست")
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name="playlist_items",
        verbose_name=_("ترک")
    )
    order = models.PositiveIntegerField(_("ترتیب"), default=0)

    class Meta:
        verbose_name = _("آیتم پلی‌لیست")
        verbose_name_plural = _("آیتم‌های پلی‌لیست")
        unique_together = ('playlist', 'track')
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=["playlist", "order"]),
        ]

    def __str__(self):
        return f"{self.track.title} in {self.playlist.title}"