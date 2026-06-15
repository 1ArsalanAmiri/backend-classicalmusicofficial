import jdatetime
from django.contrib import admin, messages
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import Subscription, SubscriptionHistory
from django.utils import timezone


# -----------------------------
# Forms
# -----------------------------
class SubscriptionAdminForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        price = cleaned_data.get("price")
        has_permanent_discount = cleaned_data.get("has_permanent_discount")
        discounted_price = cleaned_data.get("discounted_price")
        discount_label = cleaned_data.get("discount_label")

        if price is not None and price < 0:
            raise ValidationError("قیمت اشتراک نمی‌تواند منفی باشد.")

        duration_days = cleaned_data.get("duration_days")
        if duration_days is not None and duration_days <= 0:
            raise ValidationError("مدت زمان اشتراک باید بیشتر از صفر باشد.")

        if has_permanent_discount:
            if discounted_price in [None, ""]:
                raise ValidationError("وقتی تخفیف دائمی فعال است، قیمت با تخفیف باید مشخص شود.")

            if discounted_price is not None and price is not None:
                if discounted_price < 0:
                    raise ValidationError("قیمت با تخفیف نمی‌تواند منفی باشد.")

                if discounted_price >= price:
                    raise ValidationError("قیمت با تخفیف باید کمتر از قیمت اصلی باشد.")

            if not discount_label:
                cleaned_data["discount_label"] = "تخفیف ویژه"

        else:
            cleaned_data["discounted_price"] = None
            cleaned_data["discount_label"] = None

        return cleaned_data



class SubscriptionHistoryAdminForm(forms.ModelForm):
    class Meta:
        model = SubscriptionHistory
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise ValidationError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")

        return cleaned_data


# -----------------------------
# Subscription Admin
# -----------------------------
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    form = SubscriptionAdminForm

    list_display = (
        "name",
        "id",
        "price_display",
        "duration_days",
        "subscription_type",
        "discounted_price_display",
        "discount_percentage_display",
    )
    list_filter = (
        "subscription_type",
        "has_permanent_discount",
        "duration_days",
    )
    search_fields = (
        "name",
        "discount_label",
    )
    ordering = ("price", "duration_days", "name")
    list_per_page = 25
    save_on_top = True

    readonly_fields = (
        "discount_percentage",
        "discount_preview",
    )

    fieldsets = (
        ("اطلاعات اصلی اشتراک", {
            "fields": (
                "name",
                "price",
                "duration_days",
                "subscription_type",
            )
        }),
        ("تنظیمات تخفیف", {
            "fields": (
                "has_permanent_discount",
                "discounted_price",
                "discount_percentage",
                "discount_label",
                "discount_preview",
            ),
            "description": "در صورت فعال بودن تخفیف دائمی، درصد تخفیف به صورت خودکار محاسبه می‌شود."
        }),
    )

    actions = (
        "activate_discount_flag",
        "deactivate_discount_flag",
    )

    @admin.display(description="قیمت")
    def price_display(self, obj):
        return f"{obj.price:,.0f} تومان"

    @admin.display(description="قیمت با تخفیف")
    def discounted_price_display(self, obj):
        if obj.has_permanent_discount and obj.discounted_price:
            return f"{obj.discounted_price:,.0f} تومان"
        return "-"

    @admin.display(description="درصد تخفیف")
    def discount_percentage_display(self, obj):
        if obj.has_permanent_discount and obj.discount_percentage is not None:
            return f"{obj.discount_percentage}%"
        return "-"

    @admin.display(description="وضعیت تخفیف")
    def discount_status(self, obj):
        if obj.has_permanent_discount:
            # [اصلاح شد]
            return format_html('<span style="color: #198754; font-weight: bold;">{}</span>', 'فعال')
        # [اصلاح شد]
        return format_html('<span style="color: #dc3545; font-weight: bold;">{}</span>', 'غیرفعال')

    @admin.display(description="پیش‌نمایش تخفیف")
    def discount_preview(self, obj):
        if not obj.pk:
            return "پس از ذخیره، اطلاعات تخفیف نمایش داده می‌شود."

        if obj.has_permanent_discount and obj.discounted_price and obj.discount_percentage is not None:
            label = obj.discount_label or "بدون برچسب"

            formatted_price = f"{obj.price:,.0f}"
            formatted_discounted_price = f"{obj.discounted_price:,.0f}"

            return format_html(
                '<div style="line-height: 1.9;">'
                '<strong>قیمت اصلی:</strong> {} تومان<br>'
                '<strong>قیمت با تخفیف:</strong> {} تومان<br>'
                '<strong>درصد تخفیف:</strong> {}٪<br>'
                '<strong>برچسب:</strong> {}'
                '</div>',
                formatted_price,
                formatted_discounted_price,
                obj.discount_percentage,
                label
            )

        return "تخفیفی برای این اشتراک فعال نیست."

    @admin.action(description="فعال کردن فلگ تخفیف دائمی برای اشتراک‌های انتخاب‌شده")
    def activate_discount_flag(self, request, queryset):
        updated = 0
        skipped = 0

        for obj in queryset:
            if obj.discounted_price and obj.discounted_price < obj.price:
                if not obj.has_permanent_discount:
                    obj.has_permanent_discount = True
                    obj.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        self.message_user(
            request,
            f"{updated} اشتراک با موفقیت برای تخفیف دائمی فعال شد. {skipped} مورد به دلیل نداشتن قیمت تخفیف معتبر نادیده گرفته شد.",
            level=messages.SUCCESS if updated else messages.WARNING
        )

    @admin.action(description="غیرفعال کردن تخفیف دائمی برای اشتراک‌های انتخاب‌شده")
    def deactivate_discount_flag(self, request, queryset):
        updated = 0

        for obj in queryset:
            if obj.has_permanent_discount:
                obj.has_permanent_discount = False
                obj.save()
                updated += 1

        self.message_user(
            request,
            f"{updated} اشتراک با موفقیت از حالت تخفیف دائمی خارج شد.",
            level=messages.SUCCESS
        )


# -----------------------------
# SubscriptionHistory Admin
# -----------------------------
@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    form = SubscriptionHistoryAdminForm

    list_display = (
        "user_profile__user__phone_number",
        "subscription",
        "subscription_type_display",
        "start_date",
        "end_date",
        # "is_active_display",
    )
    list_filter = (
        "subscription__subscription_type",
        "subscription",
        "start_date",
        "end_date",
    )
    search_fields = (
        "user_profile__user__username",
        "user_profile__user__first_name",
        "user_profile__user__last_name",
        "subscription__name",
    )
    autocomplete_fields = (
        "subscription",
    )
    ordering = ("-start_date",)
    list_per_page = 25
    save_on_top = True

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "user_profile",
            "user_profile__user",
            "subscription",
        )

    @admin.display(description="کاربر")
    def user_display(self, obj):
        if obj.user_profile and obj.user_profile.user:
            user = obj.user_profile.user
            full_name = user.get_full_name().strip()
            if full_name:
                return f"{full_name} ({user.username})"
            return user.username
        return "کاربر نامشخص"

    @admin.display(description="نوع اشتراک")
    def subscription_type_display(self, obj):
        if obj.subscription:
            return obj.subscription.get_subscription_type_display()
        return "اشتراک نامشخص"

    @admin.display(description="وضعیت")
    def is_active_display(self, obj):
        today = jdatetime.date.today()

        start_date = obj.start_date
        end_date = obj.end_date

        if start_date and start_date > today:
            # [اصلاح شد]
            return format_html(
                '<span style="color: #fd7e14; font-weight: bold;">{}</span>', 'هنوز شروع نشده'
            )
        elif end_date is None:
            if start_date and start_date <= today:
                # [اصلاح شد]
                return format_html(
                    '<span style="color: #0d6efd; font-weight: bold;">{}</span>', 'فعال بدون تاریخ پایان'
                )
            else:
                # [اصلاح شد]
                return format_html(
                    '<span style="color: #fd7e14; font-weight: bold;">{}</span>', 'هنوز شروع نشده'
                )
        elif start_date and start_date <= today <= end_date:
            # [اصلاح شد]
            return format_html(
                '<span style="color: #198754; font-weight: bold;">{}</span>', 'فعال'
            )
        elif end_date < today:
            # [اصلاح شد]
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">{}</span>', 'منقضی‌شده'
            )
        else:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">{}</span>', 'منقضی‌شده'
            )
