from rest_framework import serializers
from .models import Order
from apps.users.serializers import UserSerializer

class OrderSerializer(serializers.ModelSerializer):
    client_detail = UserSerializer(source='client', read_only=True)
    driver_detail = UserSerializer(source='driver', read_only=True)

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ('client', 'driver', 'status', 'otp_code', 'base_cost', 'surcharges', 'platform_commission', 'driver_earnings', 'total_cost')


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            'origin_address', 'origin_latitude', 'origin_longitude', 'origin_notes',
            'destination_address', 'destination_latitude', 'destination_longitude',
            'recipient_name', 'recipient_phone', 'destination_notes',
            'weight_kg', 'dimensions_cm', 'packages_count', 'declared_value',
            'is_fragile', 'needs_cold_chain', 'is_dangerous', 'requires_signature',
            'package_photo_1', 'package_photo_2', 'vehicle_type',
            'order_type', 'scheduled_time', 'payment_method',
            'distance_km', 'estimated_duration_min'
        )


class PODUploadSerializer(serializers.ModelSerializer):
    otp_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = (
            'pod_location_photo', 'pod_package_photo', 'pod_latitude', 'pod_longitude',
            'pod_recipient_name', 'pod_recipient_id', 'otp_input'
        )
