from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
# نیازی به reverse_lazy نیست اگر لینک پروفایل را حذف کنیم
# from django.urls import reverse_lazy

from apps.accounts.models import OTPCode
from apps.profiles.models import UserProfile
# from apps.subscriptions.models import Subscription

CustomUser = get_user_model()

def get_user_subscriptions_count(self, obj):
    try:
        count = obj.subscription_set.count()
        if count > 0:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', count)
        else:
            return format_html('<span style="color: red;">بدون اشتراک</span>')
    except AttributeError:
        return format_html('<span style="color: gray;">نامشخص</span>')
    except Exception as e:
        print(f"Error getting subscription count for user {obj.id}: {e}")
        return format_html('<span style="color: gray;">خطا</span>')
get_user_subscriptions_count.short_description = 'تعداد اشتراک‌ها'

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    # خط 'user_profile_link' را از list_display حذف کنید
    list_display = ('phone_number', 'email', 'first_name', 'last_name', 'is_active', 'has_subscriptions_display', 'display_last_login')
    search_fields = ('phone_number', 'email', 'first_name', 'last_name')
    list_filter = ('is_active', 'last_login', 'date_joined')

    has_subscriptions_display = get_user_subscriptions_count

    def display_last_login(self, obj):
        return obj.last_login.strftime('%Y-%m-%d %H:%M:%S') if obj.last_login else 'Never logged in'
    display_last_login.short_description = 'آخرین ورود'
