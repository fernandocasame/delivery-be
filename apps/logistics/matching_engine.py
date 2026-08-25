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
        # Run clean up of stale offers first to prevent stuck matches
        try:
            SmartMatchingEngine.check_and_expire_stale_offers()
        except Exception as e:
            print('[get_nearby_eligible_drivers clean error]', e)
            
        max_dist_km = float(SystemParameter.get_param('max_offer_radius_km', '5.0'))
        locations_matching_vehicle = DriverLocation.objects.filter(
            driver__driver_profile__approval_status=DriverProfile.ApprovalStatus.APPROVED,
            driver__driver_profile__status=DriverProfile.Status.AVAILABLE,
            driver__driver_profile__vehicle_type=order.vehicle_type
        )
        
        # 1. Try to find drivers with matching vehicle type within the specified radius
        ranked_drivers = []
        for loc in locations_matching_vehicle:
            dist_km = haversine_distance_km(
                order.origin_latitude, order.origin_longitude,
                loc.latitude, loc.longitude
            )
            if dist_km <= max_dist_km:
                ranked_drivers.append({
                    'driver': loc.driver,
                    'distance_km': round(dist_km, 2)
                })
        
        if ranked_drivers:
            # Deduplicate by driver ID
            seen_ids = set()
            unique = [d for d in ranked_drivers if not (d['driver'].id in seen_ids or seen_ids.add(d['driver'].id))]
            unique.sort(key=lambda x: x['distance_km'])
            return unique

        # 2. Fallback: Try matching vehicle type at any distance (unlimited radius)
        ranked_drivers = []
        for loc in locations_matching_vehicle:
            dist_km = haversine_distance_km(
                order.origin_latitude, order.origin_longitude,
                loc.latitude, loc.longitude
            )
            ranked_drivers.append({
                'driver': loc.driver,
                'distance_km': round(dist_km, 2)
            })

        if ranked_drivers:
            seen_ids = set()
            unique = [d for d in ranked_drivers if not (d['driver'].id in seen_ids or seen_ids.add(d['driver'].id))]
            unique.sort(key=lambda x: x['distance_km'])
            return unique

        # 3. Fallback: Match any available approved driver in the system regardless of vehicle type or distance
        ranked_drivers = []
        locations_any_driver = DriverLocation.objects.filter(
            driver__driver_profile__approval_status=DriverProfile.ApprovalStatus.APPROVED,
            driver__driver_profile__status=DriverProfile.Status.AVAILABLE
        )
        for loc in locations_any_driver:
            dist_km = haversine_distance_km(
                order.origin_latitude, order.origin_longitude,
                loc.latitude, loc.longitude
            )
            ranked_drivers.append({
                'driver': loc.driver,
                'distance_km': round(dist_km, 2)
            })

        seen_ids = set()
        unique = [d for d in ranked_drivers if not (d['driver'].id in seen_ids or seen_ids.add(d['driver'].id))]
        unique.sort(key=lambda x: x['distance_km'])
        return unique

    @staticmethod
    def dispatch_order_offer(order: Order):
        # Prevent parallel processes by using transaction atomic
        with transaction.atomic():
            try:
                order_db = Order.objects.select_for_update().get(id=order.id)
            except Order.DoesNotExist:
                return

            # Strict guard: NEVER dispatch offers if order is not SEARCHING or is already assigned
            if order_db.status != OrderStatus.SEARCHING or order_db.driver is not None:
                return

            # Check if there is already an active PENDING offer for this order that hasn't expired
            active_pending = OrderOffer.objects.filter(
                order=order_db,
                status=OrderOffer.OfferStatus.PENDING,
                expires_at__gt=timezone.now()
            ).first()

            if active_pending:
                return

            drivers = SmartMatchingEngine.get_nearby_eligible_drivers(order_db)
            if not drivers:
                return

            # Deduplicate by driver ID
            seen_drivers = set()
            unique_drivers = []
            for item in drivers:
                if item['driver'].id not in seen_drivers:
                    seen_drivers.add(item['driver'].id)
                    unique_drivers.append(item)
            drivers = unique_drivers

            # Clear stale offers for this order and build fresh candidate sequence
            OrderOffer.objects.filter(order=order_db).delete()

            timeout_seconds = int(SystemParameter.get_param('order_offer_timeout_seconds', '15'))
            offers_to_create = []
            now = timezone.now()

            for idx, item in enumerate(drivers):
                expires = now + timedelta(seconds=timeout_seconds) if idx == 0 else now
                offers_to_create.append(
                    OrderOffer(
                        order=order_db,
                        driver=item['driver'],
                        status=OrderOffer.OfferStatus.PENDING if idx == 0 else OrderOffer.OfferStatus.EXPIRED,
                        distance_km=item['distance_km'],
                        sequence=idx,
                        expires_at=expires
                    )
                )

            OrderOffer.objects.bulk_create(offers_to_create)

            # Fetch sequence 0 offer from DB to obtain real primary key ID for Celery task
            first_offer = OrderOffer.objects.filter(order=order_db, sequence=0).first()

            if first_offer:
                # Notify the first candidate driver via Pusher
                PusherRealtimeService.trigger_new_order_available_to_driver(
                    order=order_db,
                    driver_id=first_offer.driver_id,
                    expires_at=first_offer.expires_at
                )

                try:
                    from apps.logistics.tasks import expire_order_offer
                    expire_order_offer.apply_async(args=[first_offer.id], countdown=timeout_seconds)
                except Exception as e:
                    print('[Celery schedule warning] Failed to schedule task:', e)

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

            # Immediately send retraction signal to all other drivers' screens
            other_drivers = User.objects.filter(offers__order=order).exclude(id=driver_user.id).distinct()
            for d in other_drivers:
                PusherRealtimeService.trigger_order_retracted_from_driver(order, d.id)

            return {'success': True, 'message': 'Pedido asignado con éxito', 'order_id': order.id}

    @staticmethod
    def reject_order(order_id: int, driver_user: User) -> dict:
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(id=order_id)
            except Order.DoesNotExist:
                return {'success': False, 'message': 'El pedido no existe.'}

            offer = OrderOffer.objects.filter(
                order=order,
                driver=driver_user,
                status=OrderOffer.OfferStatus.PENDING
            ).first()

            if not offer:
                return {'success': False, 'message': 'No tienes una oferta pendiente para este pedido.'}

            # Mark current offer as REJECTED
            offer.status = OrderOffer.OfferStatus.REJECTED
            offer.save()

            # Retract notification from current driver
            PusherRealtimeService.trigger_order_retracted_from_driver(order, driver_user.id)

            # Activate next offer if present
            next_offer = OrderOffer.objects.filter(
                order=order,
                sequence=offer.sequence + 1
            ).first()

            if next_offer:
                timeout_seconds = int(SystemParameter.get_param('order_offer_timeout_seconds', '15'))
                next_offer.status = OrderOffer.OfferStatus.PENDING
                next_offer.expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
                next_offer.save()

                PusherRealtimeService.trigger_new_order_available_to_driver(
                    order=order,
                    driver_id=next_offer.driver_id,
                    expires_at=next_offer.expires_at
                )

                try:
                    from apps.logistics.tasks import expire_order_offer
                    expire_order_offer.apply_async(args=[next_offer.id], countdown=timeout_seconds)
                except Exception:
                    pass
            else:
                try:
                    SmartMatchingEngine.dispatch_order_offer(order)
                except Exception:
                    pass

            return {'success': True, 'message': 'Oferta rechazada correctamente.'}

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

    @staticmethod
    def check_and_expire_stale_offers():
        # Find all pending offers that have expired
        now = timezone.now()
        try:
            stale_offers = OrderOffer.objects.filter(
                status=OrderOffer.OfferStatus.PENDING,
                expires_at__lte=now
            )
            for offer in stale_offers:
                with transaction.atomic():
                    try:
                        locked_offer = OrderOffer.objects.select_for_update().get(id=offer.id)
                    except OrderOffer.DoesNotExist:
                        continue
                        
                    if locked_offer.status != OrderOffer.OfferStatus.PENDING:
                        continue
                        
                    locked_offer.status = OrderOffer.OfferStatus.EXPIRED
                    locked_offer.save()
                    
                    PusherRealtimeService.trigger_order_retracted_from_driver(locked_offer.order, locked_offer.driver_id)
                    
                    next_offer = OrderOffer.objects.filter(
                        order=locked_offer.order,
                        sequence=locked_offer.sequence + 1
                    ).first()
                    
                    if next_offer:
                        from apps.config_params.models import SystemParameter
                        timeout_seconds = int(SystemParameter.get_param('order_offer_timeout_seconds', '15'))
                        
                        next_offer.status = OrderOffer.OfferStatus.PENDING
                        next_offer.expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
                        next_offer.save()
                        
                        PusherRealtimeService.trigger_new_order_available_to_driver(
                            order=locked_offer.order,
                            driver_id=next_offer.driver_id,
                            expires_at=next_offer.expires_at
                        )
                        
                        try:
                            from apps.logistics.tasks import expire_order_offer
                            expire_order_offer.apply_async(args=[next_offer.id], countdown=timeout_seconds)
                        except Exception:
                            pass
                    else:
                        try:
                            SmartMatchingEngine.dispatch_order_offer(locked_offer.order)
                        except Exception:
                            pass
        except Exception as e:
            print('[check_and_expire_stale_offers error]', e)

