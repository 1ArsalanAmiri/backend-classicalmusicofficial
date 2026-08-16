from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Comment, Like, Follow, Bookmark


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_related_object', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at', 'content_type')
    search_fields = ('user__username', 'user__phone_number', 'body')
    readonly_fields = ('created_at',)
    actions = ['approve_comments', 'disapprove_comments']
    autocomplete_fields = ['user']
    list_editable = ('is_approved',)
    list_per_page = 50

    fieldsets = (
        ("اطلاعات کاربر و متن", {
            'fields': ('user', 'body', 'parent')
        }),
        ("وضعیت محتوا", {
            'fields': ('content_type', 'object_id')
        }),
        ("وضعیت تایید", {
            'fields': ('is_approved', 'is_deleted')
        }),
        ("زمان ثبت", {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description="محتوا")
    def get_related_object(self, obj):
        target = obj.content_object
        if target is None:
            return "نامشخص / حذف شده"

        slug = getattr(target, "slug", None)
        label = slug or str(target)

        try:
            admin_url = reverse(
                f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                args=[target.pk]
            )
            return format_html(
                '<a href="{}">{} | {}</a>',
                admin_url,
                obj.content_type.name.capitalize(),
                label
            )
        except Exception:
            return f"{obj.content_type.name.capitalize()} | {label}"

    @admin.action(description="تایید کامنت‌های انتخاب‌شده")
    def approve_comments(self, request, queryset):
        # اجرای save روی تک‌تک اعضا جهت تریگر سیگنال update_comment_count
        count = 0
        for comment in queryset:
            comment.is_approved = True
            comment.save(update_fields=['is_approved'])
            count += 1
        self.message_user(request, f"{count} کامنت تایید شد.")

    @admin.action(description="رد/لغو تایید کامنت‌های انتخاب‌شده")
    def disapprove_comments(self, request, queryset):
        count = 0
        for comment in queryset:
            comment.is_approved = False
            comment.save(update_fields=['is_approved'])
            count += 1
        self.message_user(request, f"{count} نظر به وضعیت در انتظار بررسی تغییر یافت.")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_related_object', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number')
    autocomplete_fields = ['user']
    list_per_page = 50

    @admin.display(description="اثر/آلبوم لایک شده")
    def get_related_object(self, obj):
        target = obj.content_object
        if target is None:
            return "نامشخص / حذف شده"
        slug = getattr(target, "slug", None)
        label = slug or str(target)
        try:
            admin_url = reverse(
                f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                args=[target.pk]
            )
            return format_html(
                '<a href="{}">{} | {}</a>',
                admin_url,
                obj.content_type.name.capitalize(),
                label
            )
        except Exception:
            return f"{obj.content_type.name.capitalize()} | {label}"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_related_object', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number')
    autocomplete_fields = ['user']
    list_per_page = 50

    @admin.display(description="آرتیست/لیبل فالو شده")
    def get_related_object(self, obj):
        target = obj.content_object
        if target is None:
            return "نامشخص / حذف شده"
        slug = getattr(target, "slug", None)
        label = slug or str(target)
        try:
            admin_url = reverse(
                f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                args=[target.pk]
            )
            return format_html(
                '<a href="{}">{} | {}</a>',
                admin_url,
                obj.content_type.name.capitalize(),
                label
            )
        except Exception:
            return f"{obj.content_type.name.capitalize()} | {label}"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_related_object', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number')
    autocomplete_fields = ['user']
    list_per_page = 50

    @admin.display(description="محتوای ذخیره شده")
    def get_related_object(self, obj):
        target = obj.content_object
        if target is None:
            return "نامشخص / حذف شده"
        slug = getattr(target, "slug", None)
        label = slug or str(target)
        try:
            admin_url = reverse(
                f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                args=[target.pk]
            )
            return format_html(
                '<a href="{}">{} | {}</a>',
                admin_url,
                obj.content_type.name.capitalize(),
                label
            )
        except Exception:
            return f"{obj.content_type.name.capitalize()} | {label}"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')