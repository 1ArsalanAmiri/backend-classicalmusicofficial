# music/migrations/00XX_enable_trigram_and_backfill_search_vector.py
from django.contrib.postgres.operations import TrigramExtension
from django.contrib.postgres.search import SearchVector
from django.db import migrations


def populate_existing_search_vectors(apps, schema_editor):
    Track = apps.get_model('music', 'Track')
    Album = apps.get_model('music', 'Album')
    Track.objects.exclude(title='').update(
        search_vector=SearchVector('title', config='simple')
    )
    Album.objects.exclude(title='').update(
        search_vector=SearchVector('title', config='simple') + SearchVector('title_fa', config='simple')
    )


class Migration(migrations.Migration):

    dependencies = [
        # این خط رو با آخرین migration خودِ اپ music جایگزین کن
        # (همونی که makemigrations بالا ساخت، چون این migration بهش وابسته‌ست)
        ('music', '0022_album_search_vector_track_search_vector_and_more'),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunPython(populate_existing_search_vectors, reverse_code=migrations.RunPython.noop),
    ]
