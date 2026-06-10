from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
import jdatetime

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
        "user_display",
        "latest_subscription",
        "subscription_status",
        "subscriptions_count",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
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
        if latest:
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
        return format_html('<span style="color: red;">بدون اشتراک</span>')

    @admin.display(description="وضعیت اشتراک")
    def subscription_status(self, obj):
        latest = obj.subscriptionhistory_set.order_by("-start_date").first()
        if not latest:
            return format_html('<span style="color: red;">بدون اشتراک</span>')

        today = jdatetime.date.today()

        if latest.start_date and latest.start_date > today:
            return format_html(
                '<span style="color: orange; font-weight: bold;">هنوز شروع نشده</span>'
            )

        if latest.end_date is None:
            return format_html(
                '<span style="color: blue; font-weight: bold;">فعال بدون انقضا</span>'
            )

        if latest.start_date <= today <= latest.end_date:
            return format_html(
                '<span style="color: green; font-weight: bold;">فعال</span>'
            )

        if latest.end_date < today:
            return format_html(
                '<span style="color: red; font-weight: bold;">منقضی شده</span>'
            )

        return "-"

    @admin.display(description="اطلاعات آخرین اشتراک")
    def latest_subscription_info(self, obj):
        latest = obj.subscriptionhistory_set.order_by("-start_date").first()
        if not latest:
            return "این کاربر هنوز اشتراکی ندارد."

        end_date = latest.end_date if latest.end_date else "نامحدود"

        return format_html(
            "<div style='line-height: 2;'>"
            "<strong>اشتراک:</strong> {}<br>"
            "<strong>تاریخ شروع:</strong> {}<br>"
            "<strong>تاریخ پایان:</strong> {}<br>"
            "<strong>نوع اشتراک:</strong> {}"
            "</div>",
            latest.subscription.name,
            latest.start_date,
            end_date,
            latest.subscription.get_subscription_type_display(),
        )
