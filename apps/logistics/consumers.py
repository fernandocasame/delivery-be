import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import DriverLocation

class DriverLocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f"driver_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        lat = data.get('latitude')
        lng = data.get('longitude')
        heading = data.get('heading', 0.0)
        speed = data.get('speed', 0.0)

        if lat and lng:
            await self.update_location_in_db(lat, lng, heading, speed)

    @sync_to_async
    def update_location_in_db(self, lat, lng, heading, speed):
        loc, _ = DriverLocation.objects.get_or_create(
            driver=self.user,
            defaults={'latitude': lat, 'longitude': lng}
        )
        loc.latitude = lat
        loc.longitude = lng
        loc.heading = heading
        loc.speed = speed
        loc.save()

    async def order_offer_notification(self, event):
        await self.send(text_data=json.dumps({
            'event': 'ORDER_OFFER',
            'data': event['data']
        }))


class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f"order_{self.order_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def order_status_update(self, event):
        await self.send(text_data=json.dumps({
            'event': 'STATUS_UPDATE',
            'data': event
        }))

    async def driver_location_update(self, event):
        await self.send(text_data=json.dumps({
            'event': 'LOCATION_UPDATE',
            'data': event
        }))
