import time
from django.core.cache import cache
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Prefetch

from .models import Ticket, TicketMessage, TicketStatus
from .serializers import (
    TicketListSerializer,
    TicketDetailSerializer,
    TicketCreateSerializer,
    TicketMessageSerializer,
    TicketReplySerializer
)


def check_ticket_reply_rate_limit(user_id):
    cache_key = f"ticket_reply_rate_limit_{user_id}"
    reply_timestamps = cache.get(cache_key, [])
    now = time.time()
    valid_timestamps = [ts for ts in reply_timestamps if ts > (now - 600)]
    if len(valid_timestamps) >= 5:
        raise Throttled(detail="شما بیش از حد مجاز در ۱۰ دقیقه اخیر به تیکت پاسخ داده‌اید.")
    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, timeout=600)


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'ticket_type']
    search_fields = ['subject', 'messages__message']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):

        return Ticket.objects.filter(user=self.request.user).prefetch_related(
            Prefetch('messages', queryset=TicketMessage.objects.select_related('sender'))
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'create':
            return TicketCreateSerializer
        elif self.action == 'retrieve':
            return TicketDetailSerializer
        elif self.action == 'reply':
            return TicketReplySerializer
        return TicketListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()

        response_serializer = TicketDetailSerializer(ticket, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, pk=None):
        ticket = self.get_object()

        if ticket.status == TicketStatus.CLOSED:
            return Response(
                {"detail": "این تیکت بسته شده است و امکان ارسال پاسخ وجود ندارد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TicketReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        check_ticket_reply_rate_limit(request.user.id)

        with transaction.atomic():
            message = TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=serializer.validated_data['message']
            )
            ticket.status = TicketStatus.USER_REPLIED
            ticket.save(update_fields=['status', 'updated_at'])

        message_serializer = TicketMessageSerializer(message, context={'request': request})
        return Response(message_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        ticket = self.get_object()

        if ticket.status == TicketStatus.CLOSED:
            return Response(
                {"detail": "این تیکت از قبل بسته شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket.status = TicketStatus.CLOSED
        ticket.save(update_fields=['status', 'updated_at'])

        return Response(
            {"detail": "تیکت با موفقیت بسته شد.", "status": ticket.status},
            status=status.HTTP_200_OK
        )