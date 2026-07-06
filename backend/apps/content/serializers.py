from rest_framework import serializers
from .models import Post
from ..common.pagination import CustomMetaDataPagination


class PostSerializer(serializers.ModelSerializer):

    pagination_class = CustomMetaDataPagination

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'body', 'cover_image', 'created_at', 'updated_at']

