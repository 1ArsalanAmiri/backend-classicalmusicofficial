from rest_framework import serializers
from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    subscription_type_display = serializers.CharField(source='get_subscription_type_display', read_only=True)
    final_price = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'name', 'price', 'duration_days',
            'subscription_type', 'subscription_type_display',
            'has_permanent_discount', 'discounted_price', 'discount_percentage', 'discount_label',
            'final_price',
        ]

    def get_final_price(self, obj):
        if obj.has_permanent_discount and obj.discounted_price is not None:
            return obj.discounted_price
        return obj.price