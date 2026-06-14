from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from apps.profiles.models import UserProfile
from apps.music.models import Artist
from apps.profiles.models import ArtistProfile

User = get_user_model()

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)



@receiver(post_save, sender=Artist)
def create_artist_profile(sender, instance, created, **kwargs):
    if created:
        ArtistProfile.objects.create(artist=instance)
