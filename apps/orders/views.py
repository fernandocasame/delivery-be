from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Order, OrderStatus
from .serializers import OrderSerializer, OrderCreateSerializer, PODUploadSerializer
from apps.pricing.services import PricingEngine
from apps.logistics.matching_engine import SmartMatchingEngine
from apps.notifications.pusher_service import PusherRealtimeService


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
            from apps.logistics.models import OrderOffer
            from django.utils import timezone
            
            # Fetch order IDs where this driver has a pending active offer
            active_offer_order_ids = OrderOffer.objects.filter(
                driver=user,
                status=OrderOffer.OfferStatus.PENDING,
                expires_at__gt=timezone.now()
            ).values_list('order_id', flat=True)

            return Order.objects.filter(
                Q(driver=user) | 
                Q(id__in=active_offer_order_ids, status=OrderStatus.SEARCHING)
            ).order_by('-created_at')
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

        # Trigger sequential smart driver matching (no global broadcast)
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
            order = Order.objects.filter(pk=pk).first()
            if not order:
                return Response({'error': 'Pedido asignado no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            if not order.driver:
                order.driver = request.user
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Handle file uploads directly if provided
        if 'pod_package_photo' in request.FILES:
            order.pod_package_photo = request.FILES['pod_package_photo']
        if 'pod_location_photo' in request.FILES:
            order.pod_location_photo = request.FILES['pod_location_photo']
        if 'pod_recipient_name' in request.data:
            order.pod_recipient_name = request.data['pod_recipient_name']
        if 'pod_latitude' in request.data:
            try:
                order.pod_latitude = float(request.data['pod_latitude'])
            except (ValueError, TypeError):
                pass
        if 'pod_longitude' in request.data:
            try:
                order.pod_longitude = float(request.data['pod_longitude'])
            except (ValueError, TypeError):
                pass

        order.pod_timestamp = timezone.now()
        order.status = OrderStatus.DELIVERED
        order.is_paid = True
        order.save()

        # Transition driver back to AVAILABLE
        if hasattr(request.user, 'driver_profile'):
            profile = request.user.driver_profile
            profile.status = 'AVAILABLE'
            profile.completed_orders_count += 1
            profile.save()

        # Trigger Pusher Realtime Event for Delivered
        PusherRealtimeService.trigger_order_delivered(order)

        return Response(OrderSerializer(order).data)




class OrderPickupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.filter(pk=pk).first()
            if not order:
                return Response({'error': 'Pedido asignado no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            if not order.driver:
                order.driver = request.user
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if 'package_photo_1' in request.FILES:
            order.package_photo_1 = request.FILES['package_photo_1']
        if 'package_photo_2' in request.FILES:
            order.package_photo_2 = request.FILES['package_photo_2']
        if 'origin_latitude' in request.data:
            try:
                order.origin_latitude = float(request.data['origin_latitude'])
            except (ValueError, TypeError):
                pass
        if 'origin_longitude' in request.data:
            try:
                order.origin_longitude = float(request.data['origin_longitude'])
            except (ValueError, TypeError):
                pass

        order.status = OrderStatus.PICKED_UP
        order.save()

        # Trigger Pusher Realtime Event for Picked Up
        PusherRealtimeService.trigger_order_picked_up(order)

        return Response(OrderSerializer(order).data)




class OrderAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        result = SmartMatchingEngine.accept_order(order_id=pk, driver_user=request.user)
        if not result.get('success'):
            return Response({'error': result.get('message')}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Pedido no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        return Response(OrderSerializer(order).data)


class RunMigrationsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        import io
        import sys
        import subprocess
        from django.core.management import call_command
        from django.http import JsonResponse
        
        out = io.StringIO()
        out.write("=== Git Pull ===\n")
        try:
            res = subprocess.run(['git', 'pull', 'origin', 'main'], capture_output=True, text=True, check=True)
            out.write(res.stdout + "\n" + res.stderr + "\n")
        except Exception as e:
            out.write(f"Git pull failed: {str(e)}\n")
            
        out.write("=== Migrate ===\n")
        try:
            call_command('migrate', stdout=out, stderr=out)
        except Exception as e:
            out.write(f"Migrate failed: {str(e)}\n")
            
        result = out.getvalue()
        
        # Optional force restart
        if request.GET.get('restart') == '1':
            import threading
            import time
            def force_restart():
                time.sleep(1)
                sys.exit(0)
            threading.Thread(target=force_restart).start()
            result += "\n=== Restart Scheduled in 1 second ==="
            
        return JsonResponse({'status': 'success', 'output': result})
