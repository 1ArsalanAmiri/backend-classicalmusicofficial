from django.contrib import admin
from .models import Comment, Like, Follow


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_related_object', 'is_approved', 'is_deleted', 'created_at')
    list_filter = ('is_approved', 'is_deleted', 'content_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'body')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_comments', 'disapprove_comments']
    autocomplete_fields = ['user']
    list_editable = ('is_approved', 'is_deleted')
    list_per_page = 50

    fieldsets = (
        ("اطلاعات کاربر و متن", {
            'fields': ('user', 'body')
        }),
        ("وضعیت تایید و حذف", {
            'fields': ('is_approved', 'is_deleted')
        }),
        ("ارتباط با مدل‌ها (Generic)", {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ("زمان‌سنجی", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description="آبجکت مرتبط")
    def get_related_object(self, obj):
        if obj.content_type and obj.object_id:
            return f"{obj.content_type.name} | ID: {obj.object_id}"
        return "no objects found"

    @admin.action(description="تایید کامنت‌های انتخاب‌شده")
    def approve_comments(self, request, queryset):
        updated_count = queryset.update(is_approved=True)
        self.message_user(request, f"{updated_count} نظر با موفقیت تایید شد.")

    @admin.action(description="رد/لغو تایید کامنت‌های انتخاب‌شده")
    def disapprove_comments(self, request, queryset):
        updated_count = queryset.update(is_approved=False)
        self.message_user(request, f"{updated_count} نظر به وضعیت در انتظار بررسی (تایید نشده) تغییر یافت.")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_related_object', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number')
    autocomplete_fields = ['user']
    list_per_page = 50

    @admin.display(description="لایک شده (مورد مرتبط)")
    def get_related_object(self, obj):
        if obj.content_object:
            return f"{obj.content_type.name}: {obj.content_object}"
        return "نامشخص"


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_related_object', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('user__username', 'user__phone')
    autocomplete_fields = ['user']
    list_per_page = 50

    @admin.display(description="فالو شده (مورد مرتبط)")
    def get_related_object(self, obj):
        if obj.content_object:
            return f"{obj.content_type.name}: {obj.content_object}"
        return "نامشخص"

