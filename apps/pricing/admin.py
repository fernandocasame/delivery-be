from django.contrib import admin
from .models import VehicleTariff, SpecialSurgeRate

@admin.register(VehicleTariff)
class VehicleTariffAdmin(admin.ModelAdmin):
    list_display = ('vehicle_type', 'base_price', 'price_per_km', 'price_per_minute', 'min_price')


@admin.register(SpecialSurgeRate)
class SpecialSurgeRateAdmin(admin.ModelAdmin):
    list_display = ('name', 'multiplier', 'is_active')
