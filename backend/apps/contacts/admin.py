from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Ticket, TicketMessage, TicketStatus


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    fields = ['sender', 'message', 'created_at']
    readonly_fields = ['created_at']

    def get_extra(self, request, obj=None):
        if obj and obj.status == TicketStatus.CLOSED:
            return 0
        return 1


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'user', 'ticket_type', 'status_badge', 'updated_at', 'created_at']
    list_filter = ['status', 'ticket_type', 'created_at']
    search_fields = ['subject', 'user__username', 'user__email', 'messages__message']
    readonly_fields = ['status', 'created_at', 'updated_at']
    inlines = [TicketMessageInline]
    actions = ['mark_as_closed', 'mark_as_open']

    fieldsets = (
        (_('اطلاعات تیکت'), {
            'fields': ('user', 'ticket_type', 'subject', 'status')
        }),
        (_('تاریخ‌ها'), {
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description=_('وضعیت'))
    def status_badge(self, obj):
        colors = {
            TicketStatus.OPEN: '#e67e22',  # نارنجی
            TicketStatus.USER_REPLIED: '#3498db',  # آبی
            TicketStatus.ANSWERED: '#2ecc71',  # سبز
            TicketStatus.CLOSED: '#7f8c8d',  # خاکستری
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: bold; white-space: nowrap; display: inline-block;">{}</span>',
            color,
            obj.get_status_display()
        )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        has_new_admin_reply = False

        for instance in instances:
            if isinstance(instance, TicketMessage):
                is_new = instance.pk is None
                if is_new and not instance.sender_id:
                    instance.sender = request.user
                if is_new and instance.sender.is_staff:
                    has_new_admin_reply = True
                instance.save()
        formset.save_m2m()

        if has_new_admin_reply and form.instance.status != TicketStatus.CLOSED:
            form.instance.status = TicketStatus.ANSWERED
            form.instance.save(update_fields=['status', 'updated_at'])

    @admin.action(description=_("بستن تیکت‌های انتخاب شده"))
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(status=TicketStatus.CLOSED)
        self.message_user(request, f"{updated} تیکت با موفقیت بسته شدند.")

    @admin.action(description=_("تغییر وضعیت به منتظر پاسخ"))
    def mark_as_open(self, request, queryset):
        updated = queryset.update(status=TicketStatus.OPEN)
        self.message_user(request, f"{updated} تیکت به وضعیت منتظر پاسخ تغییر کردند.")