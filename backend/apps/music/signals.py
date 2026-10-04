import logging
from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Album, Track, AlbumZipExport

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Album)
def invalidate_album_cache(sender, instance, **kwargs):
    cache.delete_pattern("*.album_list.*")
    cache.delete(f"album_detail_{instance.slug}")


@receiver([post_save, post_delete], sender=Track)
def invalidate_album_cache_on_track_change(sender, instance, **kwargs):
    try:
        if instance.album_id:
            cache.delete(f"album_detail_{instance.album.slug}")
            cache.delete_pattern("album_list_*")
    except Album.DoesNotExist:
        pass


def delete_album_zip_cache(album):
    """
    زیپ‌های کش‌شده‌ی آلبوم را پاک می‌کند.
    قبلاً از export.zip_file.path و os.remove استفاده می‌شد؛ روی storageهای remote (مثل FTP)
    .path پیاده‌سازی نشده و NotImplementedError می‌داد و ذخیره‌ی هر ترک را می‌شکست.
    """
    for export in AlbumZipExport.objects.filter(album=album):
        if export.zip_file and export.zip_file.name:
            try:
                export.zip_file.storage.delete(export.zip_file.name)
            except Exception:
                logger.exception("Could not delete album zip file %s", export.zip_file.name)
        export.delete()


@receiver([post_save, post_delete], sender=Track)
def invalidate_album_zip_on_track_change(sender, instance, **kwargs):
    try:
        if instance.album_id:
            delete_album_zip_cache(instance.album)
    except Album.DoesNotExist:
        pass


@receiver(post_save, sender=Track)
def update_track_search_vector(sender, instance, update_fields=None, **kwargs):
    if update_fields is not None and 'title' not in update_fields:
        return
    Track.objects.filter(pk=instance.pk).update(
        search_vector=SearchVector('title', config='simple')
    )


@receiver(post_save, sender=Album)
def update_album_search_vector(sender, instance, update_fields=None, **kwargs):
    if update_fields is not None and not ({'title', 'title_fa'} & set(update_fields)):
        return
    Album.objects.filter(pk=instance.pk).update(
        search_vector=SearchVector('title', config='simple') + SearchVector('title_fa', config='simple')
    )


@receiver([post_save, post_delete], sender=Album)
@receiver([post_save, post_delete], sender=Track)
def invalidate_music_api_cache(sender, instance, **kwargs):

    cache.clear()