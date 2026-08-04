from django.db import models, transaction
from apps.common.models import TimeStampedModel, PublishStatus, unique_slugify
from apps.music.models import Track, AlbumType
from django.utils.translation import gettext_lazy as _
from django.conf import settings



def playlist_cover_path(instance, filename):
    return f"playlists/{instance.slug}/{filename}"


class Playlist(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
        verbose_name=_("کاربر"),
        null=True, blank=True
    )
    album = models.ForeignKey(
        'music.Album',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='synced_playlists',
        verbose_name=_("آلبوم ادیتوریال مرتبط")
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
    is_public = models.BooleanField(_("عمومی است؟"), default=False)
    is_editorial = models.BooleanField(_("پلی‌لیست ادیتوریال است؟"), default=False)
    tracks = models.ManyToManyField(
        Track,
        through='PlaylistItem',
        related_name='in_playlists',
        verbose_name=_("ترک‌ها")
    )

    class Meta:
        verbose_name = _("پلی‌لیست شخصی")
        verbose_name_plural = _("پلی‌لیست‌های شخصی")
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", f"{self.title}-{self.user_id}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{username} - {self.title}"

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
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.track.title} in {self.playlist.title}"


class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='playlist_tracks')
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='playlist_entries')
    order = models.PositiveIntegerField(default=0, verbose_name="Track Order")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ترک پلی لیست"
        verbose_name_plural = "ترک های پلی لیست"
        ordering = ['order']
        indexes = [
            models.Index(fields=["playlist", "order"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["playlist", "track"], name="unique_playlist_track")
        ]

    def __str__(self):
        return f"{self.playlist.title} - {self.track.title} (Order: {self.order})"


def sync_editorial_album_to_playlist(album):
    if album.album_type != AlbumType.EDITORIAL_PLAYLIST:
        return None

    with transaction.atomic():
        playlist, _ = Playlist.objects.update_or_create(
            album=album,
            defaults={
                'title': album.title,
                'title_fa': album.title_fa,
                'description': album.description,
                'cover_image': album.cover_image,
                'is_editorial': True
            }
        )

        PlaylistTrack.objects.filter(playlist=playlist).delete()

        album_tracks = album.tracks.filter(status=PublishStatus.PUBLISHED).order_by('track_number', 'id')
        new_playlist_tracks = [
            PlaylistTrack(
                playlist=playlist,
                track=track,
                order=idx + 1
            )
            for idx, track in enumerate(album_tracks)
        ]
        PlaylistTrack.objects.bulk_create(new_playlist_tracks)
        return playlist