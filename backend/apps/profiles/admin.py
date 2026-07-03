import jdatetime
from django.contrib import admin
from django.utils.html import format_html
from django.contrib.contenttypes.models import ContentType
from apps.profiles.models import UserProfile
from apps.subscriptions.models import SubscriptionHistory
from apps.interactions.models import Like, Follow
from apps.music.models import Album, Artist, Track
from apps.playlists.models import Playlist
from django.utils.safestring import mark_safe


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
        "user_display",
        "subscriptions_count",
        "latest_subscription",
        "subscription_status",
        "joined_date",
    )
    search_fields = (
        "user__username",
        "user__phone_number",
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields = ("user",)
    inlines = [SubscriptionHistoryInline]
    save_on_top = True

    fieldsets = (
        ("اطلاعات پایه", {
            "fields": ("user", "profile_image", "image_preview", "joined_date")
        }),
        ("آمار فعالیت کاربر", {
            "fields": (
                "liked_albums_stat",
                "followed_artists_stat",
                "liked_songs_stat",
                "saved_playlists_stat",
            ),
            "classes": ("collapse",),  # قابلیت جمع‌شوندگی برای خلوت ماندن ادمین
        }),
        ("اطلاعات اشتراک", {
            "fields": ("latest_subscription_info",)
        }),
    )

    readonly_fields = (
        "image_preview",
        "joined_date",
        "latest_subscription_info",
        "liked_albums_stat",
        "followed_artists_stat",
        "liked_songs_stat",
        "saved_playlists_stat",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("user").prefetch_related("subscriptionhistory_set__subscription")

    # --- متدهای نمایشی فیلدهای اطلاعات کاربر ---

    @admin.display(description="کاربر")
    def user_display(self, obj):
        full_name = obj.user.get_full_name().strip()
        identifier = obj.user.phone_number or obj.user.username
        if full_name:
            return f"{full_name} ({identifier})"
        return identifier

    @admin.display(description="پیش‌نمایش تصویر")
    def image_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; box-shadow: 0 0 5px rgba(0,0,0,0.2);" />',
                obj.profile_image.url
            )
        return mark_safe('<span style="color: gray;">بدون تصویر</span>')


    @admin.display(description="تعداد آلبوم‌های لایک‌شده")
    def liked_albums_stat(self, obj):
        ct = ContentType.objects.get_for_model(Album)
        return Like.objects.filter(user=obj.user, content_type=ct).count()

    @admin.display(description="تعداد آرتیست‌های فالوشده")
    def followed_artists_stat(self, obj):
        ct = ContentType.objects.get_for_model(Artist)
        return Follow.objects.filter(user=obj.user, content_type=ct).count()

    @admin.display(description="تعداد آهنگ‌های لایک‌شده")
    def liked_songs_stat(self, obj):
        ct = ContentType.objects.get_for_model(Track)
        return Like.objects.filter(user=obj.user, content_type=ct).count()

    @admin.display(description="تعداد پلی‌لیست‌های ذخیره‌شده")
    def saved_playlists_stat(self, obj):
        ct = ContentType.objects.get_for_model(Playlist)
        return Like.objects.filter(user=obj.user, content_type=ct).count()

    # --- متدهای مربوط به اشتراک ---

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
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', count)
        return mark_safe('<span style="color: red;">بدون اشتراک</span>')

    @admin.display(description="وضعیت اشتراک")
    def subscription_status(self, obj):
        latest = obj.subscriptionhistory_set.order_by("-start_date").first()
        if not latest:
            return mark_safe('<span style="color: red;">بدون اشتراک</span>')

        today = jdatetime.date.today()
        start_date = latest.start_date
        end_date = latest.end_date

        if start_date and start_date > today:
            return mark_safe('<span style="color: orange; font-weight: bold;">هنوز شروع نشده</span>')

        if end_date is None:
            if start_date and start_date <= today:
                return mark_safe('<span style="color: blue; font-weight: bold;">فعال بدون انقضا</span>')
            return mark_safe('<span style="color: orange; font-weight: bold;">هنوز شروع نشده</span>')

        if start_date and start_date <= today <= end_date:
            return mark_safe('<span style="color: green; font-weight: bold;">فعال</span>')

        return mark_safe('<span style="color: red; font-weight: bold;">منقضی شده</span>')

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
            "<div style='line-height: 2; padding: 10px; background-color: #f8f9fa; border-radius: 5px; border: 1px solid #ddd;'>"
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
