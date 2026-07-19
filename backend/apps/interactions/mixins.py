import time
from django.core.cache import cache
from django.db import IntegrityError
from rest_framework.exceptions import Throttled, NotAuthenticated
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.contenttypes.models import ContentType
from .models import Like, Follow, Comment, Bookmark
from .serializers import CommentSerializer

def check_comment_rate_limit(user_id):
    cache_key = f"comment_rate_limit_{user_id}"
    comment_timestamps = cache.get(cache_key, [])
    now = time.time()
    valid_timestamps = [ts for ts in comment_timestamps if ts > (now - 600)]
    if len(valid_timestamps) >= 5:
        raise Throttled(detail="شما بیش از حد مجاز کامنت ثبت کرده‌اید.")
    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, timeout=600)


class LikableMixin:
    @action(detail=True, methods=['post', 'delete'], url_path='like', permission_classes=[IsAuthenticated])
    def like_toggle(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)
        if request.method == 'POST':
            _, created = Like.objects.get_or_create(user=request.user, content_type=content_type, object_id=obj.pk)
            return Response({"message": "لایک شد."}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        deleted, _ = Like.objects.filter(user=request.user, content_type=content_type, object_id=obj.pk).delete()
        return Response({"message": "لایک برداشته شد."} if deleted else {"error": "یافت نشد."}, status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)


class FollowableMixin:
    @action(detail=True, methods=['post', 'delete'], url_path='follow')
    def follow_toggle(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise NotAuthenticated(detail="برای فالو کردن باید وارد حساب کاربری شوید.")

        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)

        if request.method == 'POST':
            try:
                follow, created = Follow.objects.get_or_create(
                    user=request.user,
                    content_type=content_type,
                    object_id=obj.pk
                )
                if created:
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
                return Response({"message": "آنفالو شد."}, status=status.HTTP_204_NO_CONTENT)
            return Response({"error": "فالویی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class BookmarkableMixin:
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='bookmark')
    def toggle_save(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)
        bookmark, created = Bookmark.objects.get_or_create(user=request.user, content_type=content_type, object_id=obj.id)
        if not created:
            bookmark.delete()
            return Response({"detail": "از لیست ذخیره‌ها حذف شد."}, status=200)
        return Response({"detail": "ذخیره شد."}, status=201)


class CommentableMixin:
    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def manage_comments(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)
        if request.method == 'GET':
            comments = Comment.objects.filter(content_type=content_type, object_id=obj.pk, is_approved=True, is_deleted=False, parent__isnull=True).prefetch_related('replies__user', 'user')
            return Response(CommentSerializer(comments, many=True).data)
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        check_comment_rate_limit(request.user.id)
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, content_type=content_type, object_id=obj.pk)
        return Response({"message": "نظر ثبت شد."}, status=status.HTTP_201_CREATED)