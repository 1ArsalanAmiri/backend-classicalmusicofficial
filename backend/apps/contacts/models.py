from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from os import path
from apps.common.models import TimeStampedModel


def validate_ticket_attachment(file):
    MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20 MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

    valid_audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.flac']
    valid_image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

    ext = path.splitext(file.name)[1].lower()

    if ext in valid_audio_extensions:
        if file.size > MAX_AUDIO_SIZE:
            raise ValidationError(_('حجم فایل صوتی نباید بیشتر از 20 مگابایت باشد.'))

    elif ext in valid_image_extensions:
        if file.size > MAX_IMAGE_SIZE:
            raise ValidationError(_('حجم تصویر نباید بیشتر از 5 مگابایت باشد.'))

    else:
        raise ValidationError(_('فرمت فایل پشتیبانی نمی‌شود. فقط ارسال عکس و فایل صوتی مجاز است.'))



class TicketCategory(models.TextChoices):
    SUPPORT = 'support', _('پشتیبانی فنی سایت')
    ARTWORK = 'artwork_request', _('درخواست آثار دلخواه (فقط کاربران با اشتراک طلایی)')


class TicketStatus(models.TextChoices):
    PENDING = 'pending', _('در انتظار پاسخ')
    ANSWERED = 'answered', _('پاسخ داده شده')
    USER_REPLIED = 'user_replied', _('کاربر پاسخ داده')
    CLOSED = 'closed', _('بسته شده')


class Ticket(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name=_('کاربر')
    )
    category = models.CharField(
        max_length=20,
        choices=TicketCategory.choices,
        default=TicketCategory.SUPPORT,
        verbose_name=_('دسته‌بندی')
    )
    subject = models.CharField(_("موضوع"), max_length=255)
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.PENDING,
        verbose_name=_('وضعیت')
    )

    class Meta:
        verbose_name = _('تیکت')
        verbose_name_plural = _('تیکت‌ها')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.subject} - {self.user.phone_number}"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('تیکت')
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name=_('ارسال کننده')
    )
    body = models.TextField(_("متن پیام"))
    attachment = models.FileField(
        upload_to="tickets/attachments/",
        blank=True,
        null=True,
        verbose_name="فایل ضمیمه"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ارسال'))

    class Meta:
        verbose_name = _('پیام تیکت')
        verbose_name_plural = _('پیام‌های تیکت')
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender.phone_number} on {self.ticket.subject}"

