from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Like, Follow, Comment



@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def update_likes_count(sender, instance, **kwargs):
    target_object = instance.content_object
    if hasattr(target_object, 'likes_count'):
        count = Like.objects.filter(
            content_type=instance.content_type,
            object_id=instance.object_id
        ).count()
        target_object.likes_count = count
        target_object.save(update_fields=['likes_count'])


@receiver(post_save, sender=Follow)
@receiver(post_delete, sender=Follow)
def update_followers_count(sender, instance, **kwargs):
    target_object = instance.content_object
    if hasattr(target_object, 'followers_count'):
        count = Follow.objects.filter(
            content_type=instance.content_type,
            object_id=instance.object_id
        ).count()
        target_object.followers_count = count
        target_object.save(update_fields=['followers_count'])


@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def update_comment_count(sender, instance, **kwargs):
    target_album = instance.album
    if hasattr(target_album, 'comments_count'):
        count = Comment.objects.filter(
            album=target_album,
            is_approved=True
        ).count()
        target_album.comments_count = count
        target_album.save(update_fields=['comments_count'])
