from django.contrib import admin
from .models import Ticket, TicketMessage, TicketStatus


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    readonly_fields = ['sender', 'created_at']
    fields = ['sender', 'body', 'attachment', 'created_at']

    def has_change_permission(self, request, obj=None):
        return False


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
