from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    is_liked = serializers.BooleanField(read_only=True, default=False)
    is_saved = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'author', 'body', 'cover_image', 'created_at', 'is_liked', 'is_saved']


class LandingPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['title', 'slug', 'author', 'cover_image']
