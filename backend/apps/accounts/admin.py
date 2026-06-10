from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import format_html

from apps.profiles.models import UserProfile

CustomUser = get_user_model()


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "profile_link",
        "subscriptions_count",
        "latest_subscription",
        "display_last_login",
    )
    search_fields = ("phone_number", "email", "first_name", "last_name")
    list_filter = ("is_active", "last_login", "date_joined")
    save_on_top = True

    @admin.display(description="پروفایل")
    def profile_link(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        if profile:
            url = reverse("admin:profiles_userprofile_change", args=[profile.pk])
            return format_html('<a href="{}">مشاهده پروفایل</a>', url)

        add_url = reverse("admin:profiles_userprofile_add")
        return format_html('<a href="{}?user={}">ساخت پروفایل</a>', add_url, obj.pk)

    @admin.display(description="تعداد اشتراک‌ها")
    def subscriptions_count(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        if not profile:
            return format_html('<span style="color: gray;">بدون پروفایل</span>')

        count = profile.subscriptionhistory_set.count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                count
            )
        return format_html('<span style="color: red;">بدون اشتراک</span>')

    @admin.display(description="آخرین اشتراک")
    def latest_subscription(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        if not profile:
            return "-"

        latest = profile.subscriptionhistory_set.order_by("-start_date").select_related("subscription").first()
        if latest:
            return latest.subscription.name
        return "-"

    @admin.display(description="آخرین ورود")
    def display_last_login(self, obj):
        return obj.last_login.strftime("%Y-%m-%d %H:%M:%S") if obj.last_login else "Never logged in"
