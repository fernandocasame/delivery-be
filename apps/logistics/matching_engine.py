import math
from django.conf import settings
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.users.models import DriverProfile, User
from apps.orders.models import Order, OrderStatus
from apps.config_params.models import SystemParameter
from .models import DriverLocation

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class SmartMatchingEngine:
    @staticmethod
    def get_nearby_eligible_drivers(order: Order) -> list:
        max_dist_km = float(SystemParameter.get_param('max_offer_radius_km', '5.0'))
        
        locations = DriverLocation.objects.filter(
            driver__driver_profile__approval_status=DriverProfile.ApprovalStatus.APPROVED,
            driver__driver_profile__status=DriverProfile.Status.AVAILABLE,
            driver__driver_profile__vehicle_type=order.vehicle_type
        )

        ranked_drivers = []
        for loc in locations:
            dist_km = haversine_distance_km(
                order.origin_latitude, order.origin_longitude,
                loc.latitude, loc.longitude
            )
            if dist_km <= max_dist_km:
                profile = loc.driver.driver_profile
                score = (profile.rating_avg * 20.0) + (10.0 / max(dist_km, 0.1)) + (profile.acceptance_rate * 0.1)
                ranked_drivers.append({
                    'driver': loc.driver,
                    'distance_km': round(dist_km, 2),
                    'score': score
                })

        ranked_drivers.sort(key=lambda x: x['score'], reverse=True)
        return ranked_drivers

    @staticmethod
    def dispatch_order_offer(order: Order):
        drivers = SmartMatchingEngine.get_nearby_eligible_drivers(order)
        channel_layer = get_channel_layer()

        offer_payload = {
            'type': 'new_order_offer',
            'order_id': order.id,
            'origin_address': order.origin_address,
            'origin_latitude': order.origin_latitude,
            'origin_longitude': order.origin_longitude,
            'destination_address': order.destination_address,
            'destination_latitude': order.destination_latitude,
            'destination_longitude': order.destination_longitude,
            'total_cost': float(order.total_cost),
            'driver_earnings': float(order.driver_earnings),
            'vehicle_type': order.vehicle_type,
            'distance_km': order.distance_km,
        }

        for item in drivers:
            driver_user = item['driver']
            async_to_sync(channel_layer.group_send)(
                f"driver_{driver_user.id}",
                {
                    'type': 'order_offer_notification',
                    'data': offer_payload
                }
            )

    @staticmethod
    def accept_order(order_id: int, driver_user: User) -> dict:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            
            if order.status != OrderStatus.SEARCHING or order.driver is not None:
                return {'success': False, 'message': 'El pedido ya fue asignado a otro repartidor.'}

            order.driver = driver_user
            order.status = OrderStatus.ACCEPTED
            order.save()

            if hasattr(driver_user, 'driver_profile'):
                profile = driver_user.driver_profile
                profile.status = DriverProfile.Status.BUSY
                profile.save()

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"order_{order.id}",
                {
                    'type': 'order_status_update',
                    'status': OrderStatus.ACCEPTED,
                    'driver_id': driver_user.id,
                    'driver_name': driver_user.get_full_name()
                }
            )

            return {'success': True, 'message': 'Pedido asignado con éxito', 'order_id': order.id}

    @staticmethod
    def check_nearby_batch_orders(driver_user: User, current_lat: float, current_lng: float) -> list:
        active_order = Order.objects.filter(driver=driver_user, status=OrderStatus.IN_TRANSIT_TO_DESTINATION).first()
        if not active_order:
            return []

        dist_to_destination_m = haversine_distance_km(
            current_lat, current_lng,
            active_order.destination_latitude, active_order.destination_longitude
        ) * 1000.0

        trigger_dist_m = float(SystemParameter.get_param('nearby_batching_trigger_distance_m', '100.0'))
        if dist_to_destination_m <= trigger_dist_m:
            nearby_orders = Order.objects.filter(
                status=OrderStatus.SEARCHING,
                driver__isnull=True,
                vehicle_type=active_order.vehicle_type
            )
            return list(nearby_orders[:3])
        return []
