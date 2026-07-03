from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.common.models import TimeStampedModel


class TicketCategory(models.TextChoices):
    SUPPORT = 'support', _('پشتیبانی عمومی')
    ARTWORK = 'artwork_request', _('درخواست آثار دلخواه (ویژه طلایی)')


class TicketStatus(models.TextChoices):
    PENDING = 'pending', _('در انتظار پاسخ پشتیبان')
    ANSWERED = 'answered', _('پاسخ داده شده')
    USER_REPLIED = 'user_replied', _('پاسخ کاربر')
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
        ordering = ['-updated_at'] # تیکت‌های جدیدتر یا تازه آپدیت شده در بالا
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
        _("فایل ضمیمه"),
        upload_to='tickets/attachments/',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ارسال'))

    class Meta:
        verbose_name = _('پیام تیکت')
        verbose_name_plural = _('پیام‌های تیکت')
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender.phone_number} on {self.ticket.subject}"
