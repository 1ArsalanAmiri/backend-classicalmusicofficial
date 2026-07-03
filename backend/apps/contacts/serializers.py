from rest_framework import serializers
from django.db import transaction
from .models import Ticket, TicketMessage, TicketCategory
from apps.subscriptions.services import get_active_subscription


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.first_name', read_only=True)
    is_admin = serializers.BooleanField(source='sender.is_staff', read_only=True)

    class Meta:
        model = TicketMessage
        fields = ['id', 'sender_name', 'is_admin', 'body', 'attachment', 'created_at']


class TicketListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'category', 'status', 'created_at', 'updated_at']


class TicketDetailSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'category', 'status', 'created_at', 'updated_at', 'messages']


class TicketCreateSerializer(serializers.ModelSerializer):
    message_body = serializers.CharField(write_only=True, required=True, help_text="متن پیام تیکت")
    attachment = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Ticket
        fields = ['category', 'subject', 'message_body', 'attachment']

    def validate(self, attrs):
        request = self.context.get('request')
        category = attrs.get('category')

        if category == TicketCategory.ARTWORK:
            sub_history = get_active_subscription(request.user)
            if not sub_history or sub_history.subscription.subscription_type not in ['both', 'all']:
                raise serializers.ValidationError({
                    "category": "برای درخواست آثار دلخواه، باید اشتراک طلایی تهیه کنید."
                })

        return attrs

    def create(self, validated_data):
        message_body = validated_data.pop('message_body')
        attachment = validated_data.pop('attachment', None)
        user = self.context['request'].user

        with transaction.atomic():
            ticket = Ticket.objects.create(user=user, **validated_data)
            TicketMessage.objects.create(
                ticket=ticket,
                sender=user,
                body=message_body,
                attachment=attachment
            )
        return ticket


class TicketReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketMessage
        fields = ['body', 'attachment']
