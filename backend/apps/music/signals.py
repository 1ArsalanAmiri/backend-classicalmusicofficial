from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Album, Track


@receiver(post_save, sender=Album)
def invalidate_album_cache(sender, instance, **kwargs):
    cache.delete_pattern("*.album_list.*")
    cache.delete(f"album_detail_{instance.slug}")


@receiver([post_save, post_delete], sender=Album)
def invalidate_album_cache(sender, instance, **kwargs):
    cache.delete_pattern("*.album_list.*")
    cache.delete(f"album_detail_{instance.slug}")

@receiver([post_save, post_delete], sender=Track)
def invalidate_album_cache_on_track_change(sender, instance, **kwargs):
    if instance.album:
        cache.delete(f"album_detail_{instance.album.slug}")
        cache.delete_pattern("*.album_list.*")