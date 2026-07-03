import mimetypes

from django.http import HttpResponse, Http404, HttpResponseForbidden
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
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


class TicketViewSet(viewsets.GenericViewSet,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.CreateModelMixin):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user).prefetch_related('messages__sender')

    def get_serializer_class(self):
        if self.action == 'create':
            return TicketCreateSerializer
        if self.action == 'retrieve':
            return TicketDetailSerializer
        if self.action == 'reply':
            return TicketReplySerializer
        return TicketListSerializer

    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, pk=None):
        ticket = self.get_object()

        if ticket.status == TicketStatus.CLOSED:
            return Response(
                {"detail": "این تیکت بسته شده است و امکان ارسال پیام جدید وجود ندارد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            body=serializer.validated_data['body'],
            attachment=serializer.validated_data.get('attachment')
        )

        ticket.status = TicketStatus.USER_REPLIED
        ticket.save(update_fields=['status', 'updated_at'])

        response_serializer = TicketMessageSerializer(message)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


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

        file_path = message.attachment.name

        response = HttpResponse()

        response['X-Accel-Redirect'] = f'/protected-media/{file_path}'

        content_type, _ = mimetypes.guess_type(file_path)
        response['Content-Type'] = content_type or 'application/octet-stream'

        # response['Content-Disposition'] = f'attachment; filename="{file_path.split("/")[-1]}"'

        return response