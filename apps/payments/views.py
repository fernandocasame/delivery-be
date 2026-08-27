import os
import json
import logging
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import DriverWallet, WalletTransaction, TransactionType, WebhookLog, PaymentLog
from .serializers import DriverWalletSerializer


logger = logging.getLogger(__name__)


class DriverWalletDetailView(generics.RetrieveAPIView):
    serializer_class = DriverWalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        wallet, _ = DriverWallet.objects.get_or_create(driver=self.request.user)
        return wallet


class PolarWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = os.environ.get('POLAR_WEBHOOK_SECRET', '')
        payload_bytes = request.body
        headers = request.headers

        event = None
        error_msg = None
        try:
            if secret:
                from polar_sdk.webhooks import validate_event, WebhookVerificationError
                event = validate_event(
                    payload=payload_bytes,
                    headers=headers,
                    secret=secret
                )
            else:
                event = json.loads(payload_bytes.decode('utf-8'))
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"[Polar Webhook Validation Fallback] {e}")
            try:
                event = json.loads(payload_bytes.decode('utf-8'))
            except Exception as json_err:
                WebhookLog.objects.create(
                    event_type='unknown',
                    provider='POLAR',
                    payload={'raw': payload_bytes.decode('utf-8', errors='ignore')},
                    status='FAILED',
                    error_message=str(json_err)
                )
                return Response({'error': 'Payload inválido'}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get('type') if isinstance(event, dict) else getattr(event, 'type', 'unknown')
        data = event.get('data', {}) if isinstance(event, dict) else getattr(event, 'data', {})

        # Save webhook log entry in DB
        webhook_log = WebhookLog.objects.create(
            event_type=event_type,
            provider='POLAR',
            payload=event if isinstance(event, dict) else data if isinstance(data, dict) else {},
            status='PROCESSED',
            error_message=error_msg
        )

        logger.info(f"[POLAR WEBHOOK LOGGED] ID: {webhook_log.id} | Event: {event_type}")

        # Process payment / checkout / subscription
        if event_type in ['order.created', 'checkout.created', 'checkout.updated', 'subscription.created', 'payment.created']:
            customer_email = None
            metadata = {}
            if isinstance(data, dict):
                customer_email = data.get('customer_email') or data.get('user', {}).get('email')
                amount_cents = data.get('amount') or data.get('net_amount') or 0
                metadata = data.get('metadata', {})
            else:
                customer_email = getattr(data, 'customer_email', None)
                amount_cents = getattr(data, 'amount', 0)
                metadata = getattr(data, 'metadata', {})

            amount = float(amount_cents) / 100.0 if isinstance(amount_cents, int) and amount_cents > 100 else float(amount_cents or 0)

            # If order checkout payment:
            order_id = metadata.get('order_id') if isinstance(metadata, dict) else None
            if order_id:
                from apps.orders.models import Order, OrderStatus
                try:
                    order = Order.objects.get(id=int(order_id))
                    order.is_paid = True
                    order.status = OrderStatus.SEARCHING
                    order.save()

                    PaymentLog.objects.create(
                        user=order.client,
                        order=order,
                        amount=amount or float(order.total_cost),
                        payment_method='POLAR',
                        status='SUCCESS',
                        description=f"Pago de Pedido #{order.id} completado vía Polar checkout ({event_type})"
                    )
                    logger.info(f"[POLAR WEBHOOK] Marked Order #{order_id} as PAID.")
                except Exception as e:
                    logger.warning(f"[Polar Webhook] Failed to process order {order_id} payment: {e}")

            # Fallback / Wallet flow
            elif customer_email:
                from apps.users.models import User
                try:
                    user = User.objects.get(email=customer_email)
                    wallet, _ = DriverWallet.objects.get_or_create(driver=user)
                    if amount > 0:
                        wallet.balance += amount
                        wallet.total_earned += amount
                        wallet.save()

                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type=TransactionType.BONUS,
                            amount=amount,
                            description=f"Pago / Recarga Polar ({event_type})"
                        )

                        PaymentLog.objects.create(
                            user=user,
                            amount=amount,
                            payment_method='POLAR',
                            status='SUCCESS',
                            description=f"Pago recibido vía Polar ({event_type})"
                        )
                    logger.info(f"[POLAR PAYMENT PROCESSED] Added ${amount} for {customer_email}")
                except User.DoesNotExist:
                    logger.warning(f"[Polar Webhook] User with email {customer_email} not found.")

        return Response({'status': 'success', 'log_id': webhook_log.id}, status=status.HTTP_200_OK)


class CreatePolarCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import requests
        token = os.environ.get('POLAR_API_TOKEN', 'polar_oat_Ym8K4i0cM5SqoOA93oq605gPvrla7g1INECmr1Oj7yB')
        product_id = os.environ.get('POLAR_PRODUCT_ID', '47138fa6-4b35-4e43-9701-d39a08e94bd8')
        env = os.environ.get('POLAR_ENV', 'sandbox')

        url = "https://sandbox-api.polar.sh/v1/checkouts/" if env == "sandbox" else "https://api.polar.sh/v1/checkouts/"

        success_url = request.data.get('success_url') or "myapp://payment/success?checkout_id={CHECKOUT_ID}"
        return_url = request.data.get('return_url') or "myapp://payment/cancel"
        order_id = request.data.get('order_id')
        customer_email = request.data.get('customer_email') or request.user.email
        amount = request.data.get('amount')
        currency = request.data.get('currency', 'usd')

        amount_cents = 360  # Default $3.60
        if amount:
            try:
                amount_cents = round(float(amount) * 100)
            except ValueError:
                pass
        elif order_id:
            try:
                from apps.orders.models import Order
                order = Order.objects.get(id=order_id)
                amount_cents = round(float(order.total_cost) * 100)
            except Exception:
                pass

        payload = {
            "products": [product_id],
            "amount": amount_cents,
            "currency": currency,
            "customer_email": customer_email,
            "metadata": {
                "order_id": str(order_id) if order_id else ""
            },
            "success_url": success_url,
            "return_url": return_url
        }

        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code not in [200, 201]:
                return Response(
                    {'error': f"Error de Polar.sh ({response.status_code}): {response.text}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            checkout = response.json()

            # Record PaymentLog in DB as PENDING
            PaymentLog.objects.create(
                user=request.user,
                order_id=order_id,
                amount=float(amount_cents) / 100.0,
                payment_method='POLAR',
                status='PENDING',
                transaction_id=str(checkout.get("id")),
                description=f"Sesión de Pago Polar iniciada (Product ID: {product_id[:8]}...)",
                raw_response=checkout
            )

            return Response({
                "checkout_id": checkout.get("id"),
                "checkout_url": checkout.get("url"),
                "amount": checkout.get("total_amount") or checkout.get("amount"),
                "currency": checkout.get("currency")
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[Polar Checkout Error]: {e}")
            return Response({'error': f"Error al generar sesión de pago en Polar: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
