from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import DriverLocation
from .serializers import DriverLocationSerializer
from .matching_engine import SmartMatchingEngine

class ActiveFleetMapListView(generics.ListAPIView):
    queryset = DriverLocation.objects.all()
    serializer_class = DriverLocationSerializer
    permission_classes = [permissions.IsAuthenticated]


class UpdateLocationRESTView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        heading = request.data.get('heading', 0.0)
        speed = request.data.get('speed', 0.0)

        if lat is None or lng is None:
            return Response({'error': 'Latitud y longitud requeridas'}, status=status.HTTP_400_BAD_REQUEST)

        loc, _ = DriverLocation.objects.get_or_create(
            driver=request.user,
            defaults={'latitude': lat, 'longitude': lng}
        )
        loc.latitude = lat
        loc.longitude = lng
        loc.heading = heading
        loc.speed = speed
        loc.save()

        # Asynchronous event-driven dispatch trigger: check for SEARCHING orders in a background thread
        if hasattr(request.user, 'driver_profile'):
            profile = request.user.driver_profile
            if profile.status == 'AVAILABLE' and profile.approval_status == 'APPROVED':
                def _async_check_dispatch():
                    try:
                        from apps.orders.models import Order, OrderStatus
                        from apps.logistics.models import OrderOffer
                        from apps.logistics.matching_engine import SmartMatchingEngine
                        from django.utils import timezone
                        
                        searching_orders = Order.objects.filter(status=OrderStatus.SEARCHING)
                        for order in searching_orders:
                            has_pending_offer = OrderOffer.objects.filter(
                                order=order,
                                status=OrderOffer.OfferStatus.PENDING,
                                expires_at__gt=timezone.now()
                            ).exists()
                            if not has_pending_offer:
                                SmartMatchingEngine.dispatch_order_offer(order)
                    except Exception as e:
                        print('[UpdateLocationRESTView order-dispatch error]', e)

                import threading
                threading.Thread(target=_async_check_dispatch, daemon=True).start()

        return Response(DriverLocationSerializer(loc).data)


class DriverAcceptOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        result = SmartMatchingEngine.accept_order(order_id, request.user)
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_409_CONFLICT)


class DriverRejectOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        result = SmartMatchingEngine.reject_order(order_id, request.user)
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

