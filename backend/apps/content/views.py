from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import Post
from .serializers import PostSerializer
from apps.interactions.mixins import LikableMixin, BookmarkableMixin, CommentableMixin


class PostViewSet(viewsets.ReadOnlyModelViewSet, LikableMixin, BookmarkableMixin,CommentableMixin):
    serializer_class = PostSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Post.objects.filter(is_published=True).order_by('-created_at')

