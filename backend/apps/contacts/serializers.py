from rest_framework import serializers
from django.db import transaction
from .models import Ticket, TicketMessage, TicketType, TicketStatus
from apps.subscriptions.services import user_has_all_access


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_admin = serializers.BooleanField(source='sender.is_staff', read_only=True)

    class Meta:
        model = TicketMessage
        fields = ['id', 'sender', 'sender_name', 'is_admin', 'message', 'created_at']
        read_only_fields = ['sender']

    def get_sender_name(self, obj):
        if not obj.sender:
            return "سیستم"
        full_name = obj.sender.get_full_name().strip()
        return full_name if full_name else obj.sender.username


class TicketListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_ticket_type_display', read_only=True)

    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'ticket_type', 'type_display', 'status', 'status_display', 'updated_at', 'created_at']


class TicketDetailSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_ticket_type_display', read_only=True)

    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'ticket_type', 'type_display', 'status', 'status_display', 'created_at', 'updated_at', 'messages']


class TicketCreateSerializer(serializers.ModelSerializer):
    message = serializers.CharField(write_only=True, required=True, label="متن پیام اولیه")

    class Meta:
        model = Ticket
        fields = ['id', 'ticket_type', 'subject', 'message']

    def validate(self, attrs):
        ticket_type = attrs.get('ticket_type')
        user = self.context['request'].user

        if ticket_type == TicketType.TRACK_REQUEST:
            if not user_has_all_access(user):
                raise serializers.ValidationError(
                    {"ticket_type": "ثبت «درخواست اثر» تنها برای کاربران دارای اشتراک طلایی امکان‌پذیر است."}
                )
        return attrs

    def create(self, validated_data):
        message_text = validated_data.pop('message')
        user = self.context['request'].user

        with transaction.atomic():
            ticket = Ticket.objects.create(user=user, status=TicketStatus.OPEN, **validated_data)
            TicketMessage.objects.create(
                ticket=ticket,
                sender=user,
                message=message_text
            )
        return ticket


class TicketReplySerializer(serializers.Serializer):
    message = serializers.CharField(required=True)