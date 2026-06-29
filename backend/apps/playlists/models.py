import uuid
from django.db import models
from django.utils.text import slugify
from apps.common.models import TimeStampedModel
from apps.music.models import Track
from django.contrib.contenttypes.fields import GenericRelation



def playlist_cover_path(instance, filename):
    return f"playlists/{instance.slug}/{filename}"


class Playlist(TimeStampedModel):
    title = models.CharField(max_length=255, verbose_name="Title")
    title_fa = models.CharField(max_length=255, verbose_name="Title FA", blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True, blank=True, verbose_name="Slug")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    cover_image = models.ImageField(upload_to=playlist_cover_path, blank=True, null=True, verbose_name="Cover Image")
    tracks = models.ManyToManyField(Track, through='PlaylistTrack', related_name='playlists', blank=True, verbose_name="Tracks")

    likes = GenericRelation('interactions.Like', related_query_name='playlist')
    follows = GenericRelation('interactions.Follow', related_query_name='playlist')

    class Meta:
        verbose_name = "پلی لیست"
        verbose_name_plural = "پلی لیست ها"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)
            if not base_slug:
                base_slug = uuid.uuid4().hex[:8]

            unique_slug = base_slug
            counter = 1
            while Playlist.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    @property
    def total_tracks(self):
        return self.playlist_tracks.count()

    @property
    def total_duration_ms(self):
        result = self.tracks.aggregate(total=models.Sum('duration_ms'))
        return result['total'] or 0


class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='playlist_tracks')
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='playlist_entries')
    order = models.PositiveIntegerField(default=0, verbose_name="Track Order")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ترک پلی لیست"
        verbose_name_plural = "ترک های پلی لیست"
        ordering = ['order']
        unique_together = ('playlist', 'track')
        indexes = [
            models.Index(fields=["playlist", "order"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["playlist", "track"], name="unique_playlist_track")
        ]

    def __str__(self):
        return f"{self.playlist.title} - {self.track.title} (Order: {self.order})"

