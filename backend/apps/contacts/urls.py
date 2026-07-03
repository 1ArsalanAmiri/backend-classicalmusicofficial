from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet
from .views import SecureTicketAttachmentView

router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='tickets')

urlpatterns = [
    path('', include(router.urls)),

    path(
        'messages/<int:message_id>/attachment/',
        SecureTicketAttachmentView.as_view(),
        name='secure-ticket-attachment'
    ),
]
