from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from apps.logistics.models import OrderOffer
from apps.orders.models import Order, OrderStatus
from apps.notifications.pusher_service import PusherRealtimeService

@shared_task
def expire_order_offer(offer_id):
    with transaction.atomic():
        try:
            offer = OrderOffer.objects.select_for_update().get(id=offer_id)
        except OrderOffer.DoesNotExist:
            return

        if offer.status != OrderOffer.OfferStatus.PENDING:
            # Already accepted, rejected, or expired
            return

        # Double check expiration time
        now = timezone.now()
        if offer.expires_at > now:
            time_left = (offer.expires_at - now).total_seconds()
            if time_left > 0.5:
                expire_order_offer.apply_async(args=[offer_id], countdown=int(time_left) + 1)
                return

        # Mark current offer as EXPIRED
        offer.status = OrderOffer.OfferStatus.EXPIRED
        offer.save()

        # Notify the current driver to remove the order from their radar
        PusherRealtimeService.trigger_order_retracted_from_driver(offer.order, offer.driver_id)

        # Find the next candidate offer for this order
        next_offer = OrderOffer.objects.filter(
            order=offer.order,
            sequence=offer.sequence + 1
        ).first()

        if next_offer:
            from apps.config_params.models import SystemParameter
            timeout_seconds = int(SystemParameter.get_param('order_offer_timeout_seconds', '15'))

            next_offer.status = OrderOffer.OfferStatus.PENDING
            next_offer.expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
            next_offer.save()

            # Notify the next driver via Pusher targeted event
            PusherRealtimeService.trigger_new_order_available_to_driver(
                order=offer.order,
                driver_id=next_offer.driver_id,
                expires_at=next_offer.expires_at
            )

            # Schedule the next expiration task
            expire_order_offer.apply_async(args=[next_offer.id], countdown=timeout_seconds)
        else:
            # No more candidates in current list. Restart matching loop to search again (can cover new/updated drivers)
            from apps.logistics.matching_engine import SmartMatchingEngine
            SmartMatchingEngine.dispatch_order_offer(offer.order)
