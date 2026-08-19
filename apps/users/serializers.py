from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DriverProfile

User = get_user_model()

class DriverProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source='user.email')
    user_name = serializers.ReadOnlyField(source='user.get_full_name')
    phone_number = serializers.ReadOnlyField(source='user.phone_number')
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = DriverProfile
        fields = '__all__'
        read_only_fields = ('approval_status', 'rejection_reason', 'rating_avg', 'total_ratings', 'acceptance_rate', 'completed_orders_count')

    def get_latitude(self, obj):
        if hasattr(obj.user, 'location') and obj.user.location:
            return obj.user.location.latitude
        return None

    def get_longitude(self, obj):
        if hasattr(obj.user, 'location') and obj.user.location:
            return obj.user.location.longitude
        return None


class UserSerializer(serializers.ModelSerializer):
    driver_profile = DriverProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'is_phone_verified', 'is_email_verified', 'profile_photo', 'driver_profile')
        read_only_fields = ('id', 'is_phone_verified', 'is_email_verified')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    vehicle_type = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    vehicle_plate = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'phone_number', 'role', 'vehicle_type', 'vehicle_plate')

    def create(self, validated_data):
        vehicle_type = validated_data.pop('vehicle_type', 'MOTO')
        vehicle_plate = validated_data.pop('vehicle_plate', '')
        password = validated_data.pop('password')

        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        if user.role == User.Role.DRIVER:
            DriverProfile.objects.create(
                user=user,
                vehicle_type=vehicle_type,
                vehicle_plate=vehicle_plate
            )

        return user


class DriverStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = ('status',)


class DriverApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = ('approval_status', 'rejection_reason')
