from django.contrib import admin
from django.utils.html import format_html
from .models import Payment, Discount, DiscountUsage


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subscription', 'formatted_amount', 'status_badge', 'ref_id', 'created_at')
    list_filter = ('status', 'created_at', 'subscription')
    search_fields = ('user__username', 'user__phone_number', 'authority', 'ref_id', 'mobile')
    readonly_fields = ('user', 'subscription', 'amount', 'discount', 'authority', 'ref_id', 'raw_request', 'raw_verify',
                       'verified_at', 'status', 'mobile')

    # جلوگیری از اضافه کردن پرداخت دستی (پرداخت فقط باید از طریق سیستم ایجاد شود)
    def has_add_permission(self, request):
        return False

    def formatted_amount(self, obj):
        return format_html('{} تومان', f"{int(obj.amount):,}")

    formatted_amount.short_description = 'مبلغ نهایی'

    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'SUCCESS': 'green',
            'FAILED': 'red',
            'CANCELED': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 5px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'وضعیت تراکنش'


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_value', 'max_uses', 'current_uses', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('code', 'name')


@admin.register(DiscountUsage)
class DiscountUsageAdmin(admin.ModelAdmin):
    list_display = ('discount', 'user', 'used_at')
    readonly_fields = ('discount', 'user', 'used_at')

    def has_add_permission(self, request):
        return False
