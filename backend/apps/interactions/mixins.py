import time
from django.core.cache import cache
from django.db import IntegrityError
from rest_framework.exceptions import Throttled
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch

from .models import Like, Follow, Comment, Bookmark
from .serializers import CommentSerializer, CommentCreateSerializer


def check_comment_rate_limit(user_id):
    cache_key = f"comment_rate_limit_{user_id}"
    comment_timestamps = cache.get(cache_key, [])
    now = time.time()
    valid_timestamps = [ts for ts in comment_timestamps if ts > (now - 600)]
    if len(valid_timestamps) >= 5:
        raise Throttled(detail="شما بیش از حد مجاز در ۱۰ دقیقه اخیر کامنت ثبت کرده‌اید.")
    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, timeout=600)


class LikableMixin:
    @action(detail=True, methods=['post', 'delete'], url_path='like', permission_classes=[IsAuthenticated])
    def like_toggle(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)

        if request.method == 'POST':
            _, created = Like.objects.get_or_create(user=request.user, content_type=content_type, object_id=obj.pk)

            # نکته: دیگر شمارنده را دستی افزایش نمی‌دهیم.
            # سیگنال update_likes_count در signals.py با هر post_save/post_delete روی Like
            # به‌صورت خودکار count واقعی را از دیتابیس می‌شمارد و ذخیره می‌کند.
            # افزایش دستی obj.likes_count اینجا باعث می‌شد نسخه‌ی stale شیء (obj)،
            # مقدار درستِ ذخیره‌شده توسط سیگنال را بلافاصله overwrite کند.

            return Response({"message": "لایک شد."}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        elif request.method == 'DELETE':
            deleted, _ = Like.objects.filter(user=request.user, content_type=content_type, object_id=obj.pk).delete()

            # همانند بالا: کسر کردن دستی کانتر حذف شد، سیگنال خودش count واقعی را می‌نویسد.

            return Response({"message": "لایک برداشته شد."} if deleted else {"error": "لایک یافت نشد."},
                            status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class FollowableMixin:
    @action(detail=True, methods=['post', 'delete'], url_path='follow', permission_classes=[IsAuthenticated])
    def follow_toggle(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)

        if request.method == 'POST':
            try:
                _, created = Follow.objects.get_or_create(
                    user=request.user,
                    content_type=content_type,
                    object_id=obj.pk
                )
                if created:
                    # نکته: افزایش دستی followers_count حذف شد.
                    # سیگنال update_followers_count در signals.py مسئول محاسبه‌ی
                    # count واقعی و ذخیره‌ی آن روی شیء تازه‌خوانده‌شده از دیتابیس است.
                    # چون get_or_create پیش از این خط، سیگنال post_save را trigger کرده،
                    # save دستی روی obj قدیمی، مقدار درستِ سیگنال را خراب می‌کرد.
                    return Response({"message": "فالو شد."}, status=status.HTTP_201_CREATED)
                return Response({"message": "شما قبلا این مورد را فالو کرده‌اید."}, status=status.HTTP_200_OK)
            except IntegrityError:
                return Response({"message": "شما قبلا این مورد را فالو کرده‌اید."}, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            deleted, _ = Follow.objects.filter(
                user=request.user,
                content_type=content_type,
                object_id=obj.pk
            ).delete()

            if deleted:
                # کاهش دستی followers_count حذف شد؛ سیگنال post_delete خودش
                # count واقعی را از دیتابیس می‌شمارد و می‌نویسد.
                return Response({"message": "آنفالو شد."}, status=status.HTTP_204_NO_CONTENT)
            return Response({"error": "فالویی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"error": "خطا ، لطفا به پشتیبانی پیام بدهید."}, status=status.HTTP_403_FORBIDDEN)


class BookmarkableMixin:
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='bookmark')
    def toggle_save(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)
        bookmark, created = Bookmark.objects.get_or_create(user=request.user, content_type=content_type,
                                                           object_id=obj.pk)
        if not created:
            bookmark.delete()
            return Response({"message": "از لیست ذخیره‌ها حذف شد."}, status=status.HTTP_200_OK)
        return Response({"message": "ذخیره شد."}, status=status.HTTP_201_CREATED)


class CommentableMixin:
    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def manage_comments(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)

        if request.method == 'GET':
            replies_qs = Comment.objects.filter(is_approved=True, is_deleted=False).select_related('user')
            comments = Comment.objects.filter(
                content_type=content_type,
                object_id=obj.pk,
                is_approved=True,
                is_deleted=False,
                parent__isnull=True
            ).select_related('user').prefetch_related(
                Prefetch('replies', queryset=replies_qs, to_attr='prefetched_replies')
            )
            return Response(CommentSerializer(comments, many=True).data)

        if not request.user.is_authenticated:
            return Response({"detail": "برای ارسال کامنت باید وارد حساب خود شوید."},
                            status=status.HTTP_401_UNAUTHORIZED)

        check_comment_rate_limit(request.user.id)
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(user=request.user, content_type=content_type, object_id=obj.pk)

        return Response({
            "message": "نظر شما با موفقیت ثبت شد و پس از تایید مدیریت نمایش داده خواهد شد.",
            "data": CommentSerializer(comment).data
        }, status=status.HTTP_201_CREATED)