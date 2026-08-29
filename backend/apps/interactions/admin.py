from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import format_html
from .models import Comment, Like, Follow, Bookmark

User = get_user_model()


class CommentReplyInline(admin.TabularInline):
    """
    اجازه می‌ده ادمین مستقیماً از داخل صفحه‌ی ویرایش یک کامنت، بهش پاسخ
    بده - بدون نیاز به دونستن content_type/object_id به‌صورت دستی.
    user، content_type و object_id توی CommentAdmin.save_formset پر
    می‌شن (نه اینجا)، چون به شیء کامنتِ والد (form.instance) نیاز دارن.
    """
    model = Comment
    fk_name = 'parent'
    extra = 1
    fields = ('body', 'is_approved', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = "پاسخ"
    verbose_name_plural = "پاسخ‌های این نظر"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_related_object', 'short_body', 'is_approved', 'has_admin_reply', 'created_at')
    list_filter = ('is_approved', 'is_deleted', 'created_at', 'content_type', 'user__is_staff')
    search_fields = ('user__username', 'user__phone_number', 'body')
    readonly_fields = ('created_at',)
    actions = ['approve_comments', 'disapprove_comments']
    autocomplete_fields = ['user']
    list_editable = ('is_approved',)
    list_per_page = 50
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    inlines = [CommentReplyInline]

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

    @admin.display(description="متن")
    def short_body(self, obj):
        text = obj.body or ""
        return text[:60] + ("…" if len(text) > 60 else "")

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

    @admin.display(description="پاسخ ادمین دارد؟", boolean=True)
    def has_admin_reply(self, obj):
        # از prefetched_replies استفاده نمی‌کنیم چون این برای صفحه‌ی لیست
        # ادمینه، نه API - یک کوئری سبک روی replies کافیه.
        if obj.parent_id is not None:
            # این خودش یک پاسخه، نه یک کامنت ریشه؛ این ستون فقط برای
            # کامنت‌های ریشه معنی داره.
            return None
        return obj.replies.filter(user__is_staff=True, is_deleted=False).exists()

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
        return super().get_queryset(request).select_related('user', 'content_type', 'parent')

    def save_formset(self, request, form, formset, change):
        """
        هندل کردن ذخیره‌ی پاسخ‌های ادمین (CommentReplyInline).
        فیلدهای user/content_type/object_id عمداً توی inline قابل‌ویرایش
        نیستن (چون نباید دستی وارد بشن) - اینجا خودکار از روی کامنتِ
        والد (form.instance) و کاربر لاگین‌شده (request.user) پر می‌شن.
        """
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Comment) and instance.pk is None:
                instance.user = request.user
                instance.content_type = form.instance.content_type
                instance.object_id = form.instance.object_id
                # پاسخ‌های ادمین به‌صورت پیش‌فرض تاییدشده ثبت میشن (چون
                # نویسنده‌شون خودِ تیم پشتیبانیه)؛ ادمین می‌تونه بعداً از
                # همون صفحه‌ی تغییر، is_approved رو خاموش کنه.
                instance.is_approved = True
            instance.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()


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