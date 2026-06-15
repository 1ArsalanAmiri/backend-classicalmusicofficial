# payments/urls.py
from django.urls import path
from .views import PaymentRequestAPIView, PaymentVerifyAPIView

app_name = 'payments'

urlpatterns = [
    path('request/', PaymentRequestAPIView.as_view(), name='request'),
    path('verify/', PaymentVerifyAPIView.as_view(), name='verify'),
]

