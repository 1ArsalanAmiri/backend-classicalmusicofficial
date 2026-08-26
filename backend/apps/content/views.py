from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, OuterRef
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import Post
from .serializers import PostSerializer
from apps.interactions.mixins import LikableMixin, BookmarkableMixin, CommentableMixin
from apps.interactions.models import Like, Bookmark


class PostViewSet(viewsets.ReadOnlyModelViewSet, LikableMixin, BookmarkableMixin, CommentableMixin):
    serializer_class = PostSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        qs = Post.objects.filter(is_published=True).order_by('-created_at')

        request = self.request
        if request and request.user.is_authenticated:
            post_content_type = ContentType.objects.get_for_model(Post)

            likes_subquery = Like.objects.filter(
                content_type=post_content_type,
                object_id=OuterRef('pk'),
                user=request.user,
            )
            bookmarks_subquery = Bookmark.objects.filter(
                content_type=post_content_type,
                object_id=OuterRef('pk'),
                user=request.user,
            )

            qs = qs.annotate(
                is_liked=Exists(likes_subquery),
                is_saved=Exists(bookmarks_subquery),
            )

        return qs