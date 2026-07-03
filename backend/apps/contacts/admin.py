from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Ticket, TicketMessage, TicketStatus


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = ('sender', 'text', 'secure_attachment_link', 'created_at')
    readonly_fields = ('sender', 'text', 'secure_attachment_link', 'created_at')

    @admin.display(description="فایل ضمیمه")
    def secure_attachment_link(self, obj):
        if obj.attachment:
            url = reverse('secure-ticket-attachment', kwargs={'message_id': obj.id})
            return format_html('<a href="{}" target="_blank" style="color: blue; text-decoration: underline;">مشاهده / دانلود فایل</a>', url)
        return mark_safe('<span style="color: gray;">بدون فایل</span>')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['subject', 'user', 'category', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['subject', 'user__phone_number', 'user__first_name']
    readonly_fields = ['user', 'category', 'subject', 'created_at', 'updated_at']
    inlines = [TicketMessageInline]
    list_editable = ['status']

    fieldsets = (
        ('اطلاعات تیکت', {
            'fields': ('user', 'category', 'subject', 'status')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_formset(self, request, form, formset, change):

        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TicketMessage):
                if not getattr(instance, 'sender_id', None):
                    instance.sender = request.user
                    instance.ticket.status = TicketStatus.ANSWERED
                    instance.ticket.save(update_fields=['status', 'updated_at'])
            instance.save()
        formset.save_m2m()
