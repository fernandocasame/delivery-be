from django.db import models
from apps.users.models import VehicleType

class VehicleTariff(models.Model):
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, unique=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    price_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=1200.00)
    price_per_minute = models.DecimalField(max_digits=10, decimal_places=2, default=200.00)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, default=6000.00)
    max_weight_kg = models.FloatField(default=20.0)
    max_volume_m3 = models.FloatField(default=0.1)

    def __str__(self):
        return f"Tarifa {self.get_vehicle_type_display()} (Base: ${self.base_price})"


class SpecialSurgeRate(models.Model):
    name = models.CharField(max_length=100) # e.g. "Recargo Lluvia", "Recargo Nocturno"
    multiplier = models.FloatField(default=1.2) # e.g. 1.2 for +20%
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - Multiplicador x{self.multiplier} [{'Activo' if self.is_active else 'Inactivo'}]"
