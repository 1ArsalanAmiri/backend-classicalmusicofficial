from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.common.models import TimeStampedModel


class TicketType(models.TextChoices):
    SUPPORT = 'support', _('پشتیبانی عمومی')
    TRACK_REQUEST = 'track_request', _('درخواست اثر')


class TicketStatus(models.TextChoices):
    OPEN = 'open', _('منتظر پاسخ ادمین')
    USER_REPLIED = 'user_replied', _('پاسخ کاربر')
    ANSWERED = 'answered', _('پاسخ داده شد')
    CLOSED = 'closed', _('بسته شده')


class Ticket(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name=_("کاربر")
    )
    ticket_type = models.CharField(
        _("نوع تیکت"),
        max_length=20,
        choices=TicketType.choices,
        default=TicketType.SUPPORT
    )
    subject = models.CharField(_("موضوع"), max_length=255)
    status = models.CharField(
        _("وضعیت"),
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True
    )

    class Meta:
        verbose_name = _("تیکت")
        verbose_name_plural = _("تیکت‌ها")
        ordering = ['-updated_at']

    def __str__(self):
        user_identifier = getattr(self.user, 'username', None) or getattr(self.user, 'phone_number', str(self.user_id))
        return f"[{self.get_ticket_type_display()}] {self.subject} - {user_identifier}"


class TicketMessage(TimeStampedModel):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_("تیکت")
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("فرستنده")
    )
    message = models.TextField(_("متن پیام"))

    class Meta:
        verbose_name = _("پیام تیکت")
        verbose_name_plural = _("پیام‌های تیکت")
        ordering = ['created_at']

    def __str__(self):
        sender_identifier = getattr(self.sender, 'username', None) or getattr(self.sender, 'phone_number', str(self.sender_id))
        return f"پیام از {sender_identifier} برای تیکت {self.ticket_id}"