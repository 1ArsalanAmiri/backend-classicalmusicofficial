from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0018_alter_artist_era'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='album',
            index=GinIndex(fields=['title_fa'], name='idx_album_title_fa_trgm', opclasses=['gin_trgm_ops']),
        ),
    ]