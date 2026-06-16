import time
from django.core.cache import cache
from django.db import IntegrityError
from rest_framework.exceptions import Throttled, NotAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.contrib.contenttypes.models import ContentType
from .models import Like, Follow, Comment
from .serializers import CommentSerializer


def check_comment_rate_limit(user_id):
    cache_key = f"comment_rate_limit_{user_id}"
    comment_timestamps = cache.get(cache_key, [])

    now = time.time()
    ten_minutes_ago = now - 600

    valid_timestamps = [ts for ts in comment_timestamps if ts > ten_minutes_ago]

    if len(valid_timestamps) >= 5:
        raise Throttled(detail="شما بیش از حد مجاز کامنت ثبت کرده‌اید. لطفاً بعدا مجددا تلاش کنید.")

    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, timeout=600)


class LikableMixin:
    @action(detail=True, methods=['post', 'delete'], url_path='like')
    def like_toggle(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise NotAuthenticated(detail="برای لایک کردن باید وارد حساب کاربری شوید.")

        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)

        if request.method == 'POST':
            try:
                like, created = Like.objects.get_or_create(
                    user=request.user,
                    content_type=content_type,
                    object_id=obj.pk
                )
                if created:
                    return Response({"message": "لایک شد."}, status=status.HTTP_201_CREATED)
                return Response({"message": "قبلا لایک شده بود."}, status=status.HTTP_200_OK)
            except IntegrityError:
                # مدیریت Race Condition
                return Response({"message": "قبلا لایک شده بود."}, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            deleted, _ = Like.objects.filter(
                user=request.user, content_type=content_type, object_id=obj.pk
            ).delete()
            if deleted:
                return Response({"message": "لایک برداشته شد."}, status=status.HTTP_204_NO_CONTENT)
            return Response({"error": "لایکی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)


class CommentableMixin:
    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def manage_comments(self, request, *args, **kwargs):
        obj = self.get_object()
        content_type = ContentType.objects.get_for_model(obj)

        if request.method == 'GET':
            comments = Comment.objects.filter(
                content_type=content_type,
                object_id=obj.pk,
                is_approved=True,
                is_deleted=False
            ).select_related('user')

            serializer = CommentSerializer(comments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'POST':
            if not request.user.is_authenticated:
                raise NotAuthenticated(detail="برای ثبت نظر باید وارد حساب کاربری شوید.")

            check_comment_rate_limit(request.user.id)

            serializer = CommentSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(
                    user=request.user,
                    content_type=content_type,
                    object_id=obj.pk
                )
                return Response({"message": "نظر ثبت شد و در انتظار تایید است."}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
