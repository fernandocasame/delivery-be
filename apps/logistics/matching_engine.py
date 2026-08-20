import math
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.users.models import DriverProfile, User
from apps.orders.models import Order, OrderStatus
from apps.config_params.models import SystemParameter
from .models import DriverLocation, OrderOffer
from apps.notifications.pusher_service import PusherRealtimeService

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
        # Search range up to 50 km to round up candidates
        max_dist_km = 50.0
        
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
                ranked_drivers.append({
                    'driver': loc.driver,
                    'distance_km': round(dist_km, 2)
                })

        # Sort strictly by distance (closest first)
        ranked_drivers.sort(key=lambda x: x['distance_km'])
        return ranked_drivers

    @staticmethod
    def dispatch_order_offer(order: Order):
        # Prevent parallel processes by using transaction atomic
        with transaction.atomic():
            # Clear any stale offers for this order
            OrderOffer.objects.filter(order=order).delete()

            drivers = SmartMatchingEngine.get_nearby_eligible_drivers(order)
            if not drivers:
                # No candidates in range, leave status as SEARCHING
                return

            timeout_seconds = int(SystemParameter.get_param('order_offer_timeout_seconds', '15'))
            
            # Pre-generate offers for all candidates in sorted sequence
            offers_to_create = []
            now = timezone.now()
            
            for idx, item in enumerate(drivers):
                # The first driver gets expires_at, other drivers have a placeholder expires_at (will be updated when activated)
                expires = now + timedelta(seconds=timeout_seconds) if idx == 0 else now
                offers_to_create.append(
                    OrderOffer(
                        order=order,
                        driver=item['driver'],
                        status=OrderOffer.OfferStatus.PENDING if idx == 0 else OrderOffer.OfferStatus.EXPIRED, # initial state
                        distance_km=item['distance_km'],
                        sequence=idx,
                        expires_at=expires
                    )
                )

            created_offers = OrderOffer.objects.bulk_create(offers_to_create)

            # Activate the first offer (sequence 0)
            first_offer = created_offers[0]
            first_offer.status = OrderOffer.OfferStatus.PENDING
            first_offer.save()

            # Notify the first driver via targeted Pusher channel
            PusherRealtimeService.trigger_new_order_available_to_driver(
                order=order,
                driver_id=first_offer.driver_id,
                expires_at=first_offer.expires_at
            )

            # Import task locally to prevent circular import issues
            from apps.logistics.tasks import expire_order_offer
            expire_order_offer.apply_async(args=[first_offer.id], countdown=timeout_seconds)

    @staticmethod
    def accept_order(order_id: int, driver_user: User) -> dict:
        with transaction.atomic():
            # Lock the order to prevent double-accept race conditions
            try:
                order = Order.objects.select_for_update().get(id=order_id)
            except Order.DoesNotExist:
                return {'success': False, 'message': 'El pedido no existe.'}
            
            if order.status != OrderStatus.SEARCHING or order.driver is not None:
                return {'success': False, 'message': 'El pedido ya fue asignado a otro repartidor.'}

            # Verify driver has a pending active offer
            active_offer = OrderOffer.objects.filter(
                order=order,
                driver=driver_user,
                status=OrderOffer.OfferStatus.PENDING,
                expires_at__gt=timezone.now()
            ).first()

            if not active_offer:
                return {'success': False, 'message': 'La oferta de este pedido ya expiró o no está disponible para ti.'}

            # Accept the offer
            active_offer.status = OrderOffer.OfferStatus.ACCEPTED
            active_offer.save()

            # Mark all other offers for this order as EXPIRED
            OrderOffer.objects.filter(order=order).exclude(id=active_offer.id).update(
                status=OrderOffer.OfferStatus.EXPIRED
            )

            # Update Order assignment
            order.driver = driver_user
            order.status = OrderStatus.ACCEPTED
            order.save()

            # Mark driver's profile status as BUSY
            if hasattr(driver_user, 'driver_profile'):
                profile = driver_user.driver_profile
                profile.status = DriverProfile.Status.BUSY
                profile.save()

            # Trigger realtime updates to Client
            PusherRealtimeService.trigger_order_accepted(order)

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
            # Only return searching orders that have an active pending offer for this driver
            from apps.logistics.models import OrderOffer
            active_offer_order_ids = OrderOffer.objects.filter(
                driver=driver_user,
                status=OrderOffer.OfferStatus.PENDING,
                expires_at__gt=timezone.now()
            ).values_list('order_id', flat=True)

            nearby_orders = Order.objects.filter(
                id__in=active_offer_order_ids,
                status=OrderStatus.SEARCHING,
                driver__isnull=True,
                vehicle_type=active_order.vehicle_type
            )
            return list(nearby_orders[:3])
        return []

