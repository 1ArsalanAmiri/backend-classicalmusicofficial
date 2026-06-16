from rest_framework import serializers
from .models import Comment
from apps.music.models import Album

class CommentSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user_info', 'body', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_user_info(self, obj):
        user = obj.user
        display_name = user.get_full_name() or getattr(user, 'username', None) or getattr(user, 'phone_number', 'کاربر ناشناس')
        return {
            "display_name": display_name,
            "username": getattr(user, 'username', None)
        }


class AlbumSerializer(serializers.ModelSerializer):
    is_liked_by_user = serializers.BooleanField(read_only=True, default=False)
    likes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'title', 'slug', 'likes_count', 'is_liked_by_user', ...]
