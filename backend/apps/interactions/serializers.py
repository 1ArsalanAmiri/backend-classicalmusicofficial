from rest_framework import serializers
from .models import Comment


class CommentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)

    def get_display_name(self, obj):
        full_name = obj.get_full_name().strip() if hasattr(obj, 'get_full_name') else ""
        if full_name:
            return full_name
        return getattr(obj, 'username', None) or str(getattr(obj, 'phone_number', obj.id))

    def get_avatar(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile or not profile.profile_image:
            return None

        image_name = profile.profile_image.name or ""
        if image_name.startswith("http://") or image_name.startswith("https://"):
            return image_name

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(profile.profile_image.url)
        return profile.profile_image.url


class CommentSerializer(serializers.ModelSerializer):
    user = CommentUserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "body",
            "parent",
            "replies",
            "is_approved",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "is_approved",
            "created_at",
        ]

    def get_replies(self, obj):
        if hasattr(obj, 'prefetched_replies'):
            replies = obj.prefetched_replies
        else:
            replies = obj.replies.filter(is_approved=True, is_deleted=False)
        return CommentSerializer(replies, many=True, context=self.context).data


class CommentCreateSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.filter(is_approved=True, is_deleted=False),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Comment
        fields = ["id", "body", "parent", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("متن کامنت نمی‌تواند خالی باشد.")
        if len(value) < 3:
            raise serializers.ValidationError("متن کامنت باید حداقل ۳ کاراکتر باشد.")
        return value