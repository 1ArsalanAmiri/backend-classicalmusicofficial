import os
from django.core.exceptions import ValidationError


def validate_archive_file(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.zip', '.rar']
    if ext not in valid_extensions:
        raise ValidationError(f'فرمت فایل مجاز نیست. فرمت‌های پشتیبانی‌شده: {", ".join(valid_extensions)}')

    max_size_mb = 1200  # قبلاً 500 بود؛ کاربر گفته فایل‌ها تا ~1 گیگ هم می‌رسن
    if value.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'حجم فایل نباید بیشتر از {max_size_mb} مگابایت باشد.')