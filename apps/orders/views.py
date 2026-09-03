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
            try:
                from apps.logistics.models import OrderOffer
                from apps.logistics.matching_engine import SmartMatchingEngine
                from django.utils import timezone
                
                # Run synchronous sweep of expired offers to advance matching sequences
                try:
                    SmartMatchingEngine.check_and_expire_stale_offers()
                except Exception as ex:
                    print('[get_queryset check_and_expire_stale_offers warning]', ex)
                
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
            except Exception as e:
                print('[DRIVER get_queryset error]', e)
                return Order.objects.filter(driver=user).order_by('-created_at')
        return Order.objects.filter(client=user, is_paid=True).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = self.perform_create(serializer)

        response_data = serializer.data
        if hasattr(order, 'checkout_url') and order.checkout_url:
            response_data['checkout_url'] = order.checkout_url

        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        data = serializer.validated_data
        payment_method = data.get('payment_method', 'CARD')

        # Calculate dynamic cost
        declared_val = data.get('declared_value')
        dist_km = data.get('distance_km') or 5.0
        est_min = data.get('estimated_duration_min') or 15.0

        if declared_val and float(declared_val) > 0:
            final_cost = Decimal(str(round(float(declared_val), 2)))
        else:
            pricing = PricingEngine.calculate_price(
                distance_km=dist_km,
                duration_minutes=est_min,
                vehicle_type=data.get('vehicle_type', 'MOTO')
            )
            final_cost = Decimal(str(pricing['total_cost']))

        commission_fee = round(final_cost * Decimal('0.15'), 2)
        driver_earnings = round(final_cost - commission_fee, 2)

        # Create Order record with is_paid = False, status = CREATED
        order = serializer.save(
            client=self.request.user,
            status=OrderStatus.CREATED,
            base_cost=Decimal('2.00'),
            surcharges=Decimal('0.00'),
            platform_commission=commission_fee,
            driver_earnings=driver_earnings,
            total_cost=final_cost,
            is_paid=False
        )

        # Generate Polar Checkout session for Card payments
        if payment_method == 'CARD':
            try:
                from apps.payments.polar_utils import create_polar_checkout
                checkout_data = create_polar_checkout(
                    order_id=order.id,
                    user=self.request.user,
                    total_cost=order.total_cost,
                    card_email=data.get('card_email'),
                    card_name=data.get('card_name'),
                )
                checkout_url = checkout_data.get("url")
                checkout_id = checkout_data.get("id")

                # Set transient checkout_url to order object
                order.checkout_url = checkout_url

                # Log in PaymentLog as PENDING
                from apps.payments.models import PaymentLog
                PaymentLog.objects.create(
                    user=self.request.user,
                    order=order,
                    amount=order.total_cost,
                    payment_method='POLAR',
                    status='PENDING',
                    transaction_id=str(checkout_id),
                    description=f"Sesión de Pago Polar iniciada para Pedido #{order.id}"
                )
            except Exception as checkout_err:
                print('[Polar Checkout Session Error in perform_create]', checkout_err)

        # Fallback to direct searching status for non-card methods (like CASH)
        else:
            order.status = OrderStatus.SEARCHING
            order.is_paid = True
            order.save()
            try:
                from apps.logistics.matching_engine import SmartMatchingEngine
                SmartMatchingEngine.dispatch_order_offer(order)
            except Exception as e:
                print('[Order Creation Matching Engine Warning]', e)

        return order




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

        if order.status in [OrderStatus.DELIVERED, OrderStatus.FINISHED, OrderStatus.CANCELLED]:
            return Response({'error': 'Este pedido ya no puede ser cancelado'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate 5% cancellation penalty & 95% refund (retaining 5%)
        original_cost = float(order.total_cost)
        cancellation_fee = round(original_cost * 0.05, 2)
        refund_amount = round(original_cost - cancellation_fee, 2)

        order.status = OrderStatus.CANCELLED
        # Charge the 5% penalty: update order total_cost to cancellation_fee
        order.total_cost = cancellation_fee
        order.is_paid = True
        order.save()

        # Update driver status back to AVAILABLE if the order was already accepted
        if order.driver:
            try:
                from apps.users.models import DriverProfile
                profile = order.driver.driver_profile
                profile.status = 'AVAILABLE'
                profile.save()
            except Exception as e:
                print('[OrderCancelView driver status update error]', e)

        return Response({
            'message': 'Pedido cancelado con éxito',
            'cancellation_fee': cancellation_fee,
            'refund_amount': refund_amount,
            'status': order.status
        })


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
        from django.http import JsonResponse
        from apps.users.models import DriverProfile
        from apps.logistics.models import DriverLocation, OrderOffer
        from apps.orders.models import Order, OrderStatus
        
        out = io.StringIO()
        out.write("=== Drivers List ===\n")
        try:
            for d in DriverProfile.objects.all():
                loc_exists = DriverLocation.objects.filter(driver=d.user).exists()
                loc_str = "None"
                if loc_exists:
                    loc = DriverLocation.objects.filter(driver=d.user).first()
                    loc_str = f"({loc.latitude}, {loc.longitude})"
                out.write(f"Driver: {d.user.email} | Status: {d.status} | Approval: {d.approval_status} | Vehicle: {d.vehicle_type} | Location: {loc_str}\n")
        except Exception as e:
            out.write(f"Driver list failed: {str(e)}\n")
            
        out.write("\n=== Searching Orders ===\n")
        try:
            for o in Order.objects.filter(status=OrderStatus.SEARCHING):
                out.write(f"Order #{o.id} | Vehicle: {o.vehicle_type} | Origin: ({o.origin_latitude}, {o.origin_longitude})\n")
        except Exception as e:
            out.write(f"Order query failed: {str(e)}\n")

        out.write("\n=== Force Dispatch Matching ===\n")
        try:
            from apps.logistics.matching_engine import SmartMatchingEngine
            for o in Order.objects.filter(status=OrderStatus.SEARCHING):
                SmartMatchingEngine.dispatch_order_offer(o)
                out.write(f"Force dispatched Order #{o.id}\n")
        except Exception as e:
            out.write(f"Force dispatch failed: {str(e)}\n")

        out.write("\n=== Order Offers in DB ===\n")
        try:
            offers = OrderOffer.objects.all()
            out.write(f"Total offers count: {offers.count()}\n")
            for o in offers:
                out.write(f"Offer ID: {o.id} | Order #{o.order_id} | Driver: {o.driver.email} | Status: {o.status} | Expires: {o.expires_at}\n")
        except Exception as e:
            out.write(f"OrderOffer query failed: {str(e)}\n")

        result = out.getvalue()
        return JsonResponse({'status': 'success', 'output': result})
