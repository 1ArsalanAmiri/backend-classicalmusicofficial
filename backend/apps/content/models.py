from django.db import models
from apps.common.models import unique_slugify # استفاده از متد موجود در پروژه

class Post(models.Model):
    title = models.CharField(max_length=255, verbose_name="عنوان")
    author = models.CharField(max_length=255, verbose_name="نویسنده",null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True, blank=True, verbose_name="اسلاگ")
    body = models.TextField(verbose_name="محتوا")
    cover_image = models.ImageField(upload_to='blog/covers/', null=True, blank=True, verbose_name="تصویر کاور")

    is_published = models.BooleanField(default=True, db_index=True, verbose_name="منتشر شده؟")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, "slug", self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title