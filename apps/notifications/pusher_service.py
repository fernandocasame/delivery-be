import logging
import os

logger = logging.getLogger(__name__)

PUSHER_APP_ID = os.environ.get('PUSHER_APP_ID', '2187556')
PUSHER_KEY = os.environ.get('PUSHER_KEY', 'e70c2ac36060ee610e6f')
PUSHER_SECRET = os.environ.get('PUSHER_SECRET', 'a0efdf09a47c69724c8a')
PUSHER_CLUSTER = os.environ.get('PUSHER_CLUSTER', 'us2')

pusher_client = None

import threading

try:
    import pusher
    pusher_client = pusher.Pusher(
        app_id=PUSHER_APP_ID,
        key=PUSHER_KEY,
        secret=PUSHER_SECRET,
        cluster=PUSHER_CLUSTER,
        ssl=True,
        timeout=2
    )
except ImportError:
    logger.warning("[Pusher] pusher python library not installed, running in mock/log mode.")
except Exception as e:
    logger.error(f"[Pusher Init Error]: {e}")


class PusherRealtimeService:
    @staticmethod
    def _send_pusher(channels, event_name, data):
        if pusher_client:
            try:
                pusher_client.trigger(channels, event_name, data)
                logger.info(f"[PUSHER TRIGGERED] Event: {event_name} on Channels: {channels}")
            except Exception as e:
                logger.error(f"[PUSHER ERROR] Failed triggering {event_name} on {channels}: {e}")
        else:
            logger.info(f"[PUSHER SIMULATED] Event: {event_name} on Channels: {channels} | Data: {data}")

    @staticmethod
    def trigger_event(channels, event_name: str, data: dict):
        """Dispatches an event to one or more Pusher channels safely in a background thread."""
        if not isinstance(channels, list):
            channels = [channels]

        thread = threading.Thread(
            target=PusherRealtimeService._send_pusher,
            args=(channels, event_name, data),
            daemon=True
        )
        thread.start()

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
        photo_url = None
        try:
            if order.package_photo_1 and order.package_photo_1.name:
                photo_url = order.package_photo_1.url
        except ValueError:
            pass

        data = {
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'status': 'IN_TRANSIT',
            'package_photo_1': photo_url,
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
        pod_url = None
        try:
            if order.pod_package_photo and order.pod_package_photo.name:
                pod_url = order.pod_package_photo.url
        except ValueError:
            pass

        data = {
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'status': 'DELIVERED',
            'pod_package_photo': pod_url,
            'title': '✅ ¡Pedido Entregado con Éxito!',
            'message': 'Tu paquete ha sido entregado correctamente.',
        }

        channels = [f"order-{order.id}"]
        if order.client_id:
            channels.append(f"client-{order.client_id}")

        cls.trigger_event(channels, 'order-delivered', data)

    @classmethod
    def trigger_new_order_available_to_driver(cls, order, driver_id, expires_at):
        """Notifies a specific driver on their private channel about a newly offered order."""
        data = {
            'event': 'new-order-available',
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
            'title': '⚡ ¡Nuevo Pedido Disponible!',
            'message': f"Recogida en {order.origin_address[:40]}",
            'expires_at': expires_at.isoformat() if expires_at else None,
        }
        cls.send_django_channels(f"driver_{driver_id}", data)
        cls.trigger_event(f"driver-{driver_id}", 'new-order-available', data)

    @classmethod
    def trigger_order_retracted_from_driver(cls, order, driver_id):
        """Notifies a specific driver to retract/remove a specific order from their radar."""
        data = {
            'event': 'order-retracted',
            'order_id': order.id,
            'formatted_id': f"H{order.id}",
            'title': 'Pedido Expirado',
            'message': 'El tiempo para aceptar el pedido ha terminado.',
        }
        cls.send_django_channels(f"driver_{driver_id}", data)
        cls.trigger_event(f"driver-{driver_id}", 'order-retracted', data)

    @staticmethod
    def send_django_channels(group_name, data):
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'order_offer_notification',
                        'data': data
                    }
                )
        except Exception as e:
            logger.warning(f"[Django Channels broadcast warning]: {e}")


