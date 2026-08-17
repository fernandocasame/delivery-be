from rest_framework import serializers
from .models import DriverLocation

class DriverLocationSerializer(serializers.ModelSerializer):
    driver_name = serializers.ReadOnlyField(source='driver.get_full_name')
    vehicle_type = serializers.ReadOnlyField(source='driver.driver_profile.vehicle_type')

    class Meta:
        model = DriverLocation
        fields = ('driver', 'driver_name', 'vehicle_type', 'latitude', 'longitude', 'heading', 'speed', 'updated_at')
