from rest_framework.permissions import BasePermission
from rest_framework import permissions
from apps.subscriptions.services import user_has_download_access, user_has_stream_access, user_has_all_access, \
    user_has_video_stream_access


class HasDownloadSubscription(BasePermission):
    message = "شما اشتراک فعال برای دانلود ندارید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_has_download_access(request.user))


class HasStreamSubscription(BasePermission):
    message = "شما اشتراک فعال برای پخش موسیقی ندارید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_has_stream_access(request.user))


class HasAllSubscription(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_has_all_access(request.user))


class IsOwnerOrPublicReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.is_public or obj.owner == request.user

        return obj.owner == request.user


class HasVideoAccessSubscription(BasePermission):
    message = "شما اشتراک فعال برای استریم یا دانلود ویدیو ندارید."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            user_has_video_stream_access(request.user)
        )