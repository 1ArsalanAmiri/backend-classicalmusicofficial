from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionViewSet, MyActiveSubscriptionView

router = DefaultRouter()
router.register(r'plans', SubscriptionViewSet, basename='subscription-plan')

urlpatterns = [
    path('me/', MyActiveSubscriptionView.as_view(), name='my-active-subscription'),
    path('', include(router.urls)),
]
