import logging
import os

logger = logging.getLogger(__name__)

PUSHER_APP_ID = os.environ.get('PUSHER_APP_ID', '2187556')
PUSHER_KEY = os.environ.get('PUSHER_KEY', 'e70c2ac36060ee610e6f')
PUSHER_SECRET = os.environ.get('PUSHER_SECRET', 'a0efdf09a47c69724c8a')
PUSHER_CLUSTER = os.environ.get('PUSHER_CLUSTER', 'us2')

pusher_client = None

try:
    import pusher
    pusher_client = pusher.Pusher(
        app_id=PUSHER_APP_ID,
        key=PUSHER_KEY,
        secret=PUSHER_SECRET,
        cluster=PUSHER_CLUSTER,
        ssl=True
    )
except ImportError:
    logger.warning("[Pusher] pusher python library not installed, running in mock/log mode.")
except Exception as e:
    logger.error(f"[Pusher Init Error]: {e}")


class PusherRealtimeService:
    @staticmethod
    def trigger_event(channels, event_name: str, data: dict):
        """Dispatches an event to one or more Pusher channels safely."""
        if not isinstance(channels, list):
            channels = [channels]

        if pusher_client:
            try:
                pusher_client.trigger(channels, event_name, data)
                logger.info(f"[PUSHER TRIGGERED] Event: {event_name} on Channels: {channels}")
            except Exception as e:
                logger.error(f"[PUSHER ERROR] Failed triggering {event_name} on {channels}: {e}")
        else:
            logger.info(f"[PUSHER SIMULATED] Event: {event_name} on Channels: {channels} | Data: {data}")

    @classmethod
    def trigger_new_order_available(cls, order):
        """Notifies all drivers on the radar channel about a newly created order."""
        data = {
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'origin': order.origin_address,
            'destination': order.destination_address,
            'cost': str(order.total_cost),
            'earnings': str(order.driver_earnings),
            'distance_km': order.distance_km,
            'weight_kg': order.weight_kg,
            'origin_latitude': order.origin_latitude,
            'origin_longitude': order.origin_longitude,
            'destination_latitude': order.destination_latitude,
            'destination_longitude': order.destination_longitude,
            'status': order.status,
            'title': '⚡ Nuevo Pedido Disponible',
            'message': f"Recogida en {order.origin_address[:40]}",
        }
        cls.trigger_event('driver-radar', 'new-order-available', data)

    @classmethod
    def trigger_order_accepted(cls, order):
        """Notifies the client that a driver has accepted their order."""
        driver_name = ""
        driver_phone = ""
        if order.driver:
            driver_name = f"{order.driver.first_name or ''} {order.driver.last_name or ''}".strip() if hasattr(order.driver, 'first_name') else ""
            if not driver_name:

                driver_name = order.driver.email.split('@')[0] if order.driver.email else "Carlos Repartidor"
            driver_phone = getattr(order.driver, 'phone_number', '+593 99 123 4567')

        if not driver_name:
            driver_name = "Carlos Repartidor (Ecobmas)"

        data = {
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'status': 'IN_TRANSIT',
            'driver_name': driver_name,
            'driver_phone': driver_phone,
            'title': '🎉 ¡Repartidor Asignado!',
            'message': f"{driver_name} ha aceptado tu pedido y va en camino a la recogida.",
        }

        channels = [f"order-{order.id}"]
        if order.client_id:
            channels.append(f"client-{order.client_id}")

        cls.trigger_event(channels, 'order-accepted', data)

    @classmethod
    def trigger_order_picked_up(cls, order):
        """Notifies the client that the package was picked up."""
        data = {
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'status': 'IN_TRANSIT',
            'package_photo_1': order.package_photo_1.url if order.package_photo_1 else None,
            'title': '📦 ¡Pedido Recogido!',
            'message': 'El motorizado retiró tu paquete y va en camino directo al destino.',
        }

        channels = [f"order-{order.id}"]
        if order.client_id:
            channels.append(f"client-{order.client_id}")

        cls.trigger_event(channels, 'order-picked-up', data)

    @classmethod
    def trigger_order_delivered(cls, order):
        """Notifies the client that the package was successfully delivered."""
        data = {
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'status': 'DELIVERED',
            'pod_package_photo': order.pod_package_photo.url if order.pod_package_photo else None,
            'title': '✅ ¡Pedido Entregado con Éxito!',
            'message': 'Tu paquete ha sido entregado correctamente.',
        }

        channels = [f"order-{order.id}"]
        if order.client_id:
            channels.append(f"client-{order.client_id}")

        cls.trigger_event(channels, 'order-delivered', data)
