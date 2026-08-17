from rest_framework import serializers
from .models import VehicleTariff, SpecialSurgeRate

class VehicleTariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleTariff
        fields = '__all__'


class SpecialSurgeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialSurgeRate
        fields = '__all__'


class PriceEstimateRequestSerializer(serializers.Serializer):
    origin_lat = serializers.FloatField()
    origin_lng = serializers.FloatField()
    destination_lat = serializers.FloatField()
    destination_lng = serializers.FloatField()
    distance_km = serializers.FloatField(required=False, default=5.0)
    duration_minutes = serializers.FloatField(required=False, default=15.0)
    vehicle_type = serializers.CharField(default='MOTO')
    is_rain = serializers.BooleanField(default=False)
    is_night = serializers.BooleanField(default=False)
