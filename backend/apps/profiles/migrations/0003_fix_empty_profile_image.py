# profiles/migrations/00XX_fix_empty_profile_image.py
from django.db import migrations


def convert_empty_string_to_null(apps, schema_editor):
    UserProfile = apps.get_model('profiles', 'UserProfile')
    UserProfile.objects.filter(profile_image='').update(profile_image=None)


class Migration(migrations.Migration):
    dependencies = [
        ('profiles', '0002_alter_userprofile_profile_image'),  # همون migrationـی که makemigrations ساخت
    ]

    operations = [
        migrations.RunPython(convert_empty_string_to_null, reverse_code=migrations.RunPython.noop),
    ]
