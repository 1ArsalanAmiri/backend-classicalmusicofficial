import os
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Album, Track, AlbumZipExport


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
    exports = AlbumZipExport.objects.filter(album=album)
    for export in exports:
        if export.zip_file and os.path.exists(export.zip_file.path):
            os.remove(export.zip_file.path)
        export.delete()


@receiver([post_save, post_delete], sender=Track)
def invalidate_album_zip_on_track_change(sender, instance, **kwargs):
    try:
        if instance.album_id:
            delete_album_zip_cache(instance.album)
    except Album.DoesNotExist:
        pass
