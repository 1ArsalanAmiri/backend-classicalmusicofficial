from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import Post
from .serializers import PostSerializer


class PostViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Post.objects.filter(is_published=True)
    serializer_class = PostSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
