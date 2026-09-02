import os
from django.conf import settings
from apps.music.models import Album, Track
from apps.common.models import PublishStatus

SLUG = "claudio-monteverdi-lorfeo"

album = Album.objects.get(slug=SLUG)
print(f"\n=== آلبوم: {album.title} (id={album.id}) ===")
print(f"MEDIA_ROOT در این کانتینر: {settings.MEDIA_ROOT}")

all_tracks = album.tracks.all()
print(f"\nتعداد کل ترک‌های این آلبوم: {all_tracks.count()}")

for t in all_tracks:
    print(f"\n--- Track #{t.id}: {t.title} ---")
    print(f"  status         : {t.status!r}   (published enum = {PublishStatus.PUBLISHED!r})")
    print(f"  status match?  : {t.status == PublishStatus.PUBLISHED}")
    print(f"  audio_file set?: {bool(t.audio_file)}")
    if t.audio_file:
        print(f"  audio_file.name: {t.audio_file.name}")
        try:
            print(f"  audio_file.path: {t.audio_file.path}")
            print(f"  فایل روی دیسک هست؟ : {os.path.exists(t.audio_file.path)}")
        except Exception as e:
            print(f"  خطا موقع خوندن path: {e}")

published_count = all_tracks.filter(status=PublishStatus.PUBLISHED).count()
print(f"\n=== نتیجه: {published_count} ترک با status منتشرشده پیدا شد ===")
