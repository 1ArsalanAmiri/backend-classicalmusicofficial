from django.contrib import admin
from .models import Comment, Like, Follow
from django.urls import reverse
from django.utils.html import format_html


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    # 'album' و 'get_album_link' حذف شدند و 'content_object' جایگزین شد
    list_display = ('user', 'get_related_object', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at', 'content_type')
    search_fields = ('user__username', 'user__phone_number', 'body')
    readonly_fields = ('created_at',)
    actions = ['approve_comments', 'disapprove_comments']

    # 'album' از autocomplete حذف شد
    autocomplete_fields = ['user']
    list_editable = ('is_approved',)
    list_per_page = 50

    fieldsets = (
        ("اطلاعات کاربر و متن", {
            'fields': ('user', 'body')
        }),
        ("وضعیت محتوا", {
            'fields': ('content_type', 'object_id')
        }),
        ("وضعیت تایید", {
            'fields': ('is_approved',)
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
        updated_count = queryset.update(is_approved=True)
        self.message_user(request, f"{updated_count} کامنت تایید شد.")

    @admin.action(description="رد/لغو تایید کامنت‌های انتخاب‌شده")
    def disapprove_comments(self, request, queryset):
        updated_count = queryset.update(is_approved=False)
        self.message_user(request, f"{updated_count} نظر به وضعیت در انتظار بررسی (تایید نشده) تغییر یافت.")

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