from rest_framework import serializers
from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    # user_avatar = serializers.ImageField(source='user.profile.avatar', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user_username', 'body', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        return super().create(validated_data)
