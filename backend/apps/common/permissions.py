from rest_framework.permissions import BasePermission
from apps.subscriptions.services import user_has_download_access, user_has_stream_access

class HasDownloadSubscription(BasePermission):
    message = "شما اشتراک فعال برای دانلود ندارید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_has_download_access(request.user))

class HasStreamSubscription(BasePermission):
    message = "شما اشتراک فعال برای پخش موسیقی ندارید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_has_stream_access(request.user))
