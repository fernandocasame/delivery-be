import random
import string
from django.db import models
from django.conf import settings
from apps.users.models import VehicleType

def generate_otp():
    return ''.join(random.choices(string.digits, k=4))


class OrderStatus(models.TextChoices):
    CREATED = 'CREATED', 'Creado'
    SEARCHING = 'SEARCHING', 'Buscando repartidor'
    ACCEPTED = 'ACCEPTED', 'Aceptado'
    IN_TRANSIT_TO_ORIGIN = 'IN_TRANSIT_TO_ORIGIN', 'En camino al origen'
    ARRIVED_ORIGIN = 'ARRIVED_ORIGIN', 'Llegó al origen'
    PICKED_UP = 'PICKED_UP', 'Recogido'
    IN_TRANSIT_TO_DESTINATION = 'IN_TRANSIT_TO_DESTINATION', 'En camino al destino'
    NEAR_DESTINATION = 'NEAR_DESTINATION', 'Cerca del destino'
    DELIVERED = 'DELIVERED', 'Entregado'
    FINISHED = 'FINISHED', 'Finalizado'
    CANCELLED = 'CANCELLED', 'Cancelado'
    FAILED = 'FAILED', 'Fallido'


class OrderType(models.TextChoices):
    IMMEDIATE = 'IMMEDIATE', 'Entrega inmediata'
    SCHEDULED = 'SCHEDULED', 'Entrega programada'


class PaymentMethod(models.TextChoices):
    CARD = 'CARD', 'Tarjeta'
    TRANSFER = 'TRANSFER', 'Transferencia'
    CASH = 'CASH', 'Efectivo'
    WALLET = 'WALLET', 'Wallet'
    CREDITS = 'CREDITS', 'Créditos'


class Order(models.Model):
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_orders')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_orders')

    status = models.CharField(max_length=30, choices=OrderStatus.choices, default=OrderStatus.CREATED)
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.IMMEDIATE)
    scheduled_time = models.DateTimeField(null=True, blank=True)

    # Origin & Destination
    origin_address = models.CharField(max_length=255)
    origin_latitude = models.FloatField()
    origin_longitude = models.FloatField()
    origin_notes = models.TextField(blank=True, null=True)

    destination_address = models.CharField(max_length=255)
    destination_latitude = models.FloatField()
    destination_longitude = models.FloatField()
    recipient_name = models.CharField(max_length=100)
    recipient_phone = models.CharField(max_length=20)
    destination_notes = models.TextField(blank=True, null=True)

    # Package details
    weight_kg = models.FloatField(default=1.0)
    dimensions_cm = models.CharField(max_length=50, blank=True, null=True)
    packages_count = models.IntegerField(default=1)
    declared_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_fragile = models.BooleanField(default=False)
    needs_cold_chain = models.BooleanField(default=False)
    is_dangerous = models.BooleanField(default=False)
    requires_signature = models.BooleanField(default=False)

    package_photo_1 = models.ImageField(upload_to='orders/packages/', null=True, blank=True)
    package_photo_2 = models.ImageField(upload_to='orders/packages/', null=True, blank=True)

    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.MOTO)

    # Financial details
    distance_km = models.FloatField(default=0.0)
    estimated_duration_min = models.FloatField(default=0.0)
    base_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    surcharges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    driver_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CARD)
    is_paid = models.BooleanField(default=False)

    # Security & OTP
    otp_code = models.CharField(max_length=6, default=generate_otp)

    # Proof of Delivery (POD)
    pod_location_photo = models.ImageField(upload_to='orders/pod/', null=True, blank=True)
    pod_package_photo = models.ImageField(upload_to='orders/pod/', null=True, blank=True)
    pod_latitude = models.FloatField(null=True, blank=True)
    pod_longitude = models.FloatField(null=True, blank=True)
    pod_timestamp = models.DateTimeField(null=True, blank=True)
    pod_recipient_name = models.CharField(max_length=100, null=True, blank=True)
    pod_recipient_id = models.CharField(max_length=30, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pedido #{self.id} [{self.status}] - Cliente: {self.client.email}"
