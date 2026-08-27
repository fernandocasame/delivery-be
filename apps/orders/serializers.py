from rest_framework import serializers
from .models import Order
from apps.users.serializers import UserSerializer

class OrderSerializer(serializers.ModelSerializer):
    client_detail = UserSerializer(source='client', read_only=True)
    driver_detail = UserSerializer(source='driver', read_only=True)
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ('client', 'driver', 'status', 'otp_code', 'base_cost', 'surcharges', 'platform_commission', 'driver_earnings', 'total_cost')

    def get_expires_at(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated and request.user.role == 'DRIVER':
            try:
                from apps.logistics.models import OrderOffer
                from django.utils import timezone
                offer = OrderOffer.objects.filter(
                    order=obj,
                    driver=request.user,
                    status=OrderOffer.OfferStatus.PENDING,
                    expires_at__gt=timezone.now()
                ).first()
                if offer:
                    return offer.expires_at.isoformat()
            except Exception as e:
                print('[OrderSerializer get_expires_at error]', e)
        return None


class OrderCreateSerializer(serializers.ModelSerializer):
    card_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    card_expiry = serializers.CharField(write_only=True, required=False, allow_blank=True)
    card_cvv = serializers.CharField(write_only=True, required=False, allow_blank=True)
    card_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    card_email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    checkout_url = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'total_cost', 'driver_earnings',
            'origin_address', 'origin_latitude', 'origin_longitude', 'origin_notes',
            'destination_address', 'destination_latitude', 'destination_longitude',
            'recipient_name', 'recipient_phone', 'destination_notes',
            'weight_kg', 'dimensions_cm', 'packages_count', 'declared_value',
            'is_fragile', 'needs_cold_chain', 'is_dangerous', 'requires_signature',
            'package_photo_1', 'package_photo_2', 'vehicle_type',
            'order_type', 'scheduled_time', 'payment_method',
            'distance_km', 'estimated_duration_min',
            'card_number', 'card_expiry', 'card_cvv', 'card_name', 'card_email',
            'checkout_url'
        )

    def create(self, validated_data):
        validated_data.pop('card_number', None)
        validated_data.pop('card_expiry', None)
        validated_data.pop('card_cvv', None)
        validated_data.pop('card_name', None)
        validated_data.pop('card_email', None)
        return super().create(validated_data)



class PODUploadSerializer(serializers.ModelSerializer):
    otp_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = (
            'pod_location_photo', 'pod_package_photo', 'pod_latitude', 'pod_longitude',
            'pod_recipient_name', 'pod_recipient_id', 'otp_input'
        )
