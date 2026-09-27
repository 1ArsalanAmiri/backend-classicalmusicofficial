from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Subscription
from .serializers import SubscriptionSerializer


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subscription.objects.all().order_by('price')
    serializer_class = SubscriptionSerializer
    permission_classes = [AllowAny]
