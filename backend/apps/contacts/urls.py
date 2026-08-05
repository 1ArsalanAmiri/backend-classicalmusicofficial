from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet

router = DefaultRouter()
router.register(r'', TicketViewSet, basename='ticket')

app_name = 'tickets'

urlpatterns = [
    path('api/v1/', include(router.urls)),
]