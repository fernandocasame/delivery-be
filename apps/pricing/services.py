from decimal import Decimal
from .models import VehicleTariff, SpecialSurgeRate
from apps.config_params.models import SystemParameter

class PricingEngine:
    @staticmethod
    def calculate_price(distance_km: float, duration_minutes: float, vehicle_type: str, is_night: bool = False, is_rain: bool = False, is_holiday: bool = False) -> dict:
        try:
            tariff = VehicleTariff.objects.get(vehicle_type=vehicle_type)
            base_price = tariff.base_price
            price_km = tariff.price_per_km
            price_min = tariff.price_per_minute
            min_price = tariff.min_price
        except VehicleTariff.DoesNotExist:
            base_price = Decimal('5000.00')
            price_km = Decimal('1200.00')
            price_min = Decimal('200.00')
            min_price = Decimal('6000.00')

        dist_cost = Decimal(str(round(distance_km, 2))) * price_km
        time_cost = Decimal(str(round(duration_minutes, 2))) * price_min

        subtotal = base_price + dist_cost + time_cost

        # Calculate surcharges
        surcharges = Decimal('0.00')

        if is_night:
            night_pct = Decimal(SystemParameter.get_param('night_surcharge_percentage', '15.0'))
            surcharges += subtotal * (night_pct / Decimal('100.0'))

        if is_rain:
            rain_pct = Decimal(SystemParameter.get_param('rain_surcharge_percentage', '20.0'))
            surcharges += subtotal * (rain_pct / Decimal('100.0'))

        if is_holiday:
            holiday_pct = Decimal(SystemParameter.get_param('holiday_surcharge_percentage', '15.0'))
            surcharges += subtotal * (holiday_pct / Decimal('100.0'))

        # Check active surge multipliers
        active_surges = SpecialSurgeRate.objects.filter(is_active=True)
        for surge in active_surges:
            subtotal = subtotal * Decimal(str(surge.multiplier))

        total = max(subtotal + surcharges, min_price)

        commission_pct = Decimal(SystemParameter.get_param('platform_commission_percentage', '15.0'))
        platform_fee = round(total * (commission_pct / Decimal('100.0')), 2)
        driver_earnings = round(total - platform_fee, 2)

        return {
            'base_price': float(base_price),
            'distance_km': round(distance_km, 2),
            'distance_cost': float(round(dist_cost, 2)),
            'duration_minutes': round(duration_minutes, 2),
            'duration_cost': float(round(time_cost, 2)),
            'surcharges': float(round(surcharges, 2)),
            'subtotal': float(round(subtotal, 2)),
            'total_cost': float(round(total, 2)),
            'platform_fee': float(platform_fee),
            'driver_earnings': float(driver_earnings),
        }
