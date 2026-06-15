import jdatetime
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone

from .models import UserProfile
from apps.subscriptions.models import SubscriptionHistory


class SubscriptionHistoryInline(admin.TabularInline):
    model = SubscriptionHistory
    extra = 0
    autocomplete_fields = ("subscription",)
    fields = ("subscription", "start_date", "end_date")
    ordering = ("-start_date",)
    verbose_name = "تاریخچه اشتراک"
    verbose_name_plural = "تاریخچه اشتراک‌ها"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user__phone_number",
        "latest_subscription",
        "subscription_status",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields = ("user",)
    inlines = [SubscriptionHistoryInline]
    save_on_top = True

    fieldsets = (
        ("اطلاعات کاربر", {
            "fields": ("user",)
        }),
        ("اطلاعات اشتراک", {
            "fields": (
                "latest_subscription_info",
            )
        }),
    )

    readonly_fields = ("latest_subscription_info",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("user").prefetch_related("subscriptionhistory_set__subscription")

    @admin.display(description="کاربر")
    def user_display(self, obj):
        full_name = obj.user.get_full_name().strip()
        if full_name:
            return f"{full_name} ({obj.user.username})"
        return obj.user.username

    @admin.display(description="آخرین اشتراک")
    def latest_subscription(self, obj):
        latest = obj.subscriptionhistory_set.order_by("-start_date").first()
        if latest and latest.subscription:
            return latest.subscription.name
        return "-"

    @admin.display(description="تعداد اشتراک‌ها")
    def subscriptions_count(self, obj):
        count = obj.subscriptionhistory_set.count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                count
            )
        # [اصلاح شد]
        return format_html('<span style="color: red;">{}</span>', 'بدون اشتراک')

    @admin.display(description="وضعیت اشتراک")
    def subscription_status(self, obj):
        latest = obj.subscriptionhistory_set.order_by("-start_date").first()
        if not latest:
            # [اصلاح شد]
            return format_html('<span style="color: red;">{}</span>', 'بدون اشتراک')

        today = jdatetime.date.today()

        start_date = latest.start_date
        end_date = latest.end_date

        if start_date and start_date > today:
            # [اصلاح شد]
            return format_html(
                '<span style="color: orange; font-weight: bold;">{}</span>', 'هنوز شروع نشده'
            )

        if end_date is None:
            if start_date and start_date <= today:
                # [اصلاح شد]
                return format_html(
                    '<span style="color: blue; font-weight: bold;">{}</span>', 'فعال بدون انقضا'
                )
            else:
                # [اصلاح شد]
                return format_html(
                    '<span style="color: orange; font-weight: bold;">{}</span>', 'هنوز شروع نشده'
                )

        if start_date and start_date <= today <= end_date:
            # [اصلاح شد]
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>', 'فعال'
            )

        if end_date < today:
            # [اصلاح شد]
            return format_html(
                '<span style="color: red; font-weight: bold;">{}</span>', 'منقضی شده'
            )

        # [اصلاح شد]
        return format_html('<span style="color: red; font-weight: bold;">{}</span>', 'منقضی شده')

    @admin.display(description="اطلاعات آخرین اشتراک")
    def latest_subscription_info(self, obj):
        latest = obj.subscriptionhistory_set.order_by("-start_date").first()
        if not latest:
            return "این کاربر هنوز اشتراکی ندارد."

        if not latest.subscription:
            return "اطلاعات اشتراک ناقص است."

        end_date_display = latest.end_date if latest.end_date else "نامحدود"
        sub_name = latest.subscription.name
        sub_type = latest.subscription.get_subscription_type_display()

        return format_html(
            "<div style='line-height: 2;'>"
            "<strong>اشتراک:</strong> {}<br>"
            "<strong>تاریخ شروع:</strong> {}<br>"
            "<strong>تاریخ پایان:</strong> {}<br>"
            "<strong>نوع اشتراک:</strong> {}"
            "</div>",
            sub_name,
            latest.start_date,
            end_date_display,
            sub_type,
        )
