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

        # Double check if the order is STILL searching and unassigned
        order = offer.order
        if order.status != OrderStatus.SEARCHING or order.driver is not None:
            # Order was already accepted by someone else! Expire this offer and stop immediately.
            offer.status = OrderOffer.OfferStatus.EXPIRED
            offer.save()
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
        PusherRealtimeService.trigger_order_retracted_from_driver(order, offer.driver_id)

        # Check AGAIN under fresh DB refresh if order is still SEARCHING
        order.refresh_from_db()
        if order.status != OrderStatus.SEARCHING or order.driver is not None:
            return

        # Find the next candidate offer for this order
        next_offer = OrderOffer.objects.filter(
            order=order,
            sequence=offer.sequence + 1
        ).first()

        from apps.config_params.models import SystemParameter
        timeout_seconds = int(SystemParameter.get_param('order_offer_timeout_seconds', '15'))

        if next_offer:
            next_offer.status = OrderOffer.OfferStatus.PENDING
            next_offer.expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
            next_offer.save()

            # Notify the next driver via Pusher targeted event
            PusherRealtimeService.trigger_new_order_available_to_driver(
                order=order,
                driver_id=next_offer.driver_id,
                expires_at=next_offer.expires_at
            )

            # Schedule the next expiration task
            expire_order_offer.apply_async(args=[next_offer.id], countdown=timeout_seconds)
        else:
            # Reached end of sequence list! Cycle back to Sequence 0 (Round-Robin)
            seq0_offer = OrderOffer.objects.filter(order=order, sequence=0).first()
            if seq0_offer:
                seq0_offer.status = OrderOffer.OfferStatus.PENDING
                seq0_offer.expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
                seq0_offer.save()

                PusherRealtimeService.trigger_new_order_available_to_driver(
                    order=order,
                    driver_id=seq0_offer.driver_id,
                    expires_at=seq0_offer.expires_at
                )

                expire_order_offer.apply_async(args=[seq0_offer.id], countdown=timeout_seconds)
            else:
                # Re-dispatch to re-evaluate active drivers
                from apps.logistics.matching_engine import SmartMatchingEngine
                SmartMatchingEngine.dispatch_order_offer(order)


@shared_task
def sweep_expired_offers():
    """Periodic Celery Beat task running every 5s to sweep and expire offers whose 15s timer passed."""
    now = timezone.now()
    expired_offers = OrderOffer.objects.filter(
        status=OrderOffer.OfferStatus.PENDING,
        expires_at__lte=now
    )
    for offer in expired_offers:
        try:
            expire_order_offer.delay(offer.id)
        except Exception as e:
            print('[sweep_expired_offers error]', e)

