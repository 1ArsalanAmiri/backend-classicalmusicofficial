from rest_framework import serializers


class TestResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    status = serializers.CharField()
