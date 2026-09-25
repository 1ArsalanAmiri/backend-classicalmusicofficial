from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription
from .serializers import SubscriptionSerializer
from .services import get_active_subscription


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subscription.objects.all().order_by('price')
    serializer_class = SubscriptionSerializer
    permission_classes = [AllowAny]


class MyActiveSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active = get_active_subscription(request.user)
        if not active:
            return Response({"has_active_subscription": False, "subscription": None})

        return Response({
            "has_active_subscription": True,
            "subscription": SubscriptionSerializer(active.subscription).data,
            "start_date": active.start_date.strftime('%Y-%m-%d') if active.start_date else None,
            "end_date": active.end_date.strftime('%Y-%m-%d') if active.end_date else None,
        })