import mimetypes

from django.http import HttpResponse, Http404, HttpResponseForbidden
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView

from .models import Ticket, TicketMessage, TicketStatus
from .serializers import (
    TicketListSerializer,
    TicketDetailSerializer,
    TicketCreateSerializer,
    TicketReplySerializer,
    TicketMessageSerializer
)


class TicketViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user).prefetch_related('messages__sender')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status == TicketStatus.CLOSED:
            return Response({"detail": "تیکت بسته شده است."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = TicketReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = TicketMessage.objects.create(ticket=ticket, sender=request.user, **serializer.validated_data)
        ticket.status = TicketStatus.USER_REPLIED
        ticket.save(update_fields=['status', 'updated_at'])
        return Response(TicketMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class SecureTicketAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, message_id):
        try:
            message = TicketMessage.objects.get(id=message_id)
        except TicketMessage.DoesNotExist:
            raise Http404("پیام یافت نشد.")

        if message.ticket.user != request.user and not request.user.is_staff:
            return HttpResponseForbidden("شما اجازه دسترسی به این فایل را ندارید.")

        if not message.attachment:
            raise Http404("این پیام فایلی ندارد.")

        response = HttpResponse()
        response['X-Accel-Redirect'] = f'/protected-media/{message.attachment.name}'
        return response
