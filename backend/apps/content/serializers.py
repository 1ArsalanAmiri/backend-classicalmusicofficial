from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'author', 'body', 'cover_image', 'created_at', 'is_liked', 'is_saved']

    def get_is_liked(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.likes.filter(user=user).exists()
        return False

    def get_is_saved(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.bookmarks.filter(user=user).exists()
        return False