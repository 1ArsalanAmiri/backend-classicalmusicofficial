from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.interactions.models import Like, Bookmark, Comment
from .models import Post


@receiver(post_delete, sender=Post)
def cleanup_post_interactions(sender, instance, **kwargs):
    post_ct = ContentType.objects.get_for_model(Post)
    Like.objects.filter(content_type=post_ct, object_id=instance.pk).delete()
    Bookmark.objects.filter(content_type=post_ct, object_id=instance.pk).delete()
    Comment.objects.filter(content_type=post_ct, object_id=instance.pk).delete()