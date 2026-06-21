from rest_framework import serializers
from .models import Comment
from apps.music.models import Album

# class CommentSerializer(serializers.ModelSerializer):
#     user_info = serializers.SerializerMethodField(read_only=True)
#
#     class Meta:
#         model = Comment
#         fields = ['id', 'user_info', 'body', 'created_at']
#         read_only_fields = ['id', 'created_at']
#
#     def get_user_info(self, obj):
#         user = obj.user
#         display_name = user.get_full_name() or getattr(user, 'username', None) or getattr(user, 'phone_number', 'کاربر ناشناس')
#         return {
#             "display_name": display_name,
#             "username": getattr(user, 'username', None)
#         }


class AlbumSerializer(serializers.ModelSerializer):
    is_liked_by_user = serializers.BooleanField(read_only=True, default=False)
    likes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'title', 'slug', 'likes_count', 'is_liked_by_user', ...]


class CommentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)


class CommentSerializer(serializers.ModelSerializer):
    user = CommentUserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "body",
            "is_approved",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "is_approved",
            "created_at",
        ]


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = [
            "id",
            "body",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_body(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("متن کامنت نمی‌تواند خالی باشد.")

        if len(value) < 3:
            raise serializers.ValidationError("متن کامنت بیش از حد کوتاه است.")

        return value
