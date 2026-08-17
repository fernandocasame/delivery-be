from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Order, OrderStatus
from .serializers import OrderSerializer, OrderCreateSerializer, PODUploadSerializer
from apps.pricing.services import PricingEngine
from apps.logistics.matching_engine import SmartMatchingEngine

class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            return Order.objects.all().order_by('-created_at')
        elif user.role == 'DRIVER':
            from django.db.models import Q
            return Order.objects.filter(Q(driver=user) | Q(driver__isnull=True, status__in=[OrderStatus.CREATED, OrderStatus.SEARCHING])).order_by('-created_at')
        return Order.objects.filter(client=user).order_by('-created_at')

    def perform_create(self, serializer):
        data = serializer.validated_data
        pricing = PricingEngine.calculate_price(
            distance_km=data.get('distance_km', 5.0),
            duration_minutes=data.get('estimated_duration_min', 15.0),
            vehicle_type=data.get('vehicle_type', 'MOTO')
        )

        order = serializer.save(
            client=self.request.user,
            status=OrderStatus.SEARCHING,
            base_cost=pricing['base_price'],
            surcharges=pricing['surcharges'],
            platform_commission=pricing['platform_fee'],
            driver_earnings=pricing['driver_earnings'],
            total_cost=pricing['total_cost']
        )

        # Trigger smart driver matching asynchronously
        SmartMatchingEngine.dispatch_order_offer(order)


class OrderDetailView(generics.RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, client=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Pedido no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if order.status in [OrderStatus.CREATED, OrderStatus.SEARCHING]:
            order.status = OrderStatus.CANCELLED
            order.save()
            return Response({'message': 'Pedido cancelado con éxito'})
        return Response({'error': 'No se puede cancelar un pedido que ya fue aceptado'}, status=status.HTTP_400_BAD_REQUEST)


class CompleteDeliveryPODView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, driver=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Pedido asignado no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PODUploadSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            otp_input = request.data.get('otp_input')
            if order.requires_signature or otp_input:
                if otp_input != order.otp_code:
                    return Response({'error': 'Código OTP de entrega incorrecto'}, status=status.HTTP_400_BAD_REQUEST)

            order.pod_timestamp = timezone.now()
            order.status = OrderStatus.DELIVERED
            serializer.save()

            # Transition driver back to AVAILABLE
            if hasattr(request.user, 'driver_profile'):
                profile = request.user.driver_profile
                profile.status = 'AVAILABLE'
                profile.completed_orders_count += 1
                profile.save()

            order.status = OrderStatus.FINISHED
            order.is_paid = True
            order.save()

            return Response(OrderSerializer(order).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrderAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Pedido no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [OrderStatus.CREATED, OrderStatus.SEARCHING]:
            return Response({'error': 'Este pedido ya fue tomado por otro repartidor'}, status=status.HTTP_400_BAD_REQUEST)

        order.driver = request.user
        order.status = OrderStatus.ACCEPTED
        order.save()
        return Response(OrderSerializer(order).data)

