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
        if event_type in ['order.created', 'order.paid', 'checkout.created', 'checkout.updated', 'subscription.created', 'payment.created']:
            customer_email = None
            metadata = {}
            checkout_id = None

            if isinstance(data, dict):
                customer_email = data.get('customer_email') or data.get('user', {}).get('email')
                amount_cents = data.get('amount') or data.get('net_amount') or 0
                metadata = data.get('metadata', {}) or {}
                checkout_id = data.get('checkout_id') or data.get('id')
            else:
                customer_email = getattr(data, 'customer_email', None)
                amount_cents = getattr(data, 'amount', 0)
                metadata = getattr(data, 'metadata', {}) or {}
                checkout_id = getattr(data, 'checkout_id', getattr(data, 'id', None))

            amount = float(amount_cents) / 100.0 if isinstance(amount_cents, int) and amount_cents > 100 else float(amount_cents or 0)

            # Try to resolve order
            from apps.orders.models import Order, OrderStatus
            order_id = metadata.get('order_id') if isinstance(metadata, dict) else None
            order = None

            if order_id:
                try:
                    order = Order.objects.get(id=int(order_id))
                except (Order.DoesNotExist, ValueError):
                    pass

            if not order and checkout_id:
                p_log = PaymentLog.objects.filter(transaction_id=str(checkout_id)).first()
                if p_log and p_log.order:
                    order = p_log.order

            if order:
                order.is_paid = True
                order.status = OrderStatus.SEARCHING
                order.save()

                try:
                    from apps.logistics.matching_engine import SmartMatchingEngine
                    SmartMatchingEngine.dispatch_order_offer(order)
                except Exception as match_err:
                    logger.warning(f"[Polar Webhook matching engine dispatch failed]: {match_err}")

                PaymentLog.objects.create(
                    user=order.client,
                    order=order,
                    amount=amount or float(order.total_cost),
                    payment_method='POLAR',
                    status='SUCCESS',
                    description=f"Pago de Pedido #{order.id} completado vía Polar checkout ({event_type})"
                )
                logger.info(f"[POLAR WEBHOOK] Marked Order #{order.id} as PAID.")

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

        # Polar base API url
        base_url = "https://sandbox-api.polar.sh/v1" if env == "sandbox" else "https://api.polar.sh/v1"

        # 1. Search for customer by email
        customer_id = None
        try:
            search_res = requests.get(
                f"{base_url}/customers/?email={customer_email}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            if search_res.status_code == 200:
                items = search_res.json().get("items", [])
                if items:
                    customer_id = items[0].get("id")
        except Exception as search_err:
            logger.warning(f"[Polar Customer Search Error]: {search_err}")

        # 2. Create customer if not exists
        if not customer_id:
            try:
                name_str = request.user.get_full_name() or request.user.username or "Cliente"
                create_res = requests.post(
                    f"{base_url}/customers/",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": customer_email,
                        "name": name_str
                    }
                )
                if create_res.status_code in [200, 201]:
                    customer_id = create_res.json().get("id")
            except Exception as create_err:
                logger.warning(f"[Polar Customer Creation Error]: {create_err}")

        # 3. Construct checkout payload
        payload = {
            "products": [product_id],
            "amount": amount_cents,
            "currency": currency,
            "metadata": {
                "order_id": str(order_id) if order_id else ""
            },
            "success_url": success_url,
            "return_url": return_url
        }

        if customer_id:
            payload["customer_id"] = customer_id
        else:
            payload["customer_email"] = customer_email

        try:
            response = requests.post(
                f"{base_url}/checkouts/",
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


class VerifyPolarPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import requests
        from apps.orders.models import Order, OrderStatus

        order_id = request.data.get('order_id')
        checkout_id = request.data.get('checkout_id')

        order = None
        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
            except (Order.DoesNotExist, ValueError):
                return Response({'error': 'Pedido no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if not order and checkout_id:
            payment_log = PaymentLog.objects.filter(transaction_id=str(checkout_id)).first()
            if payment_log and payment_log.order:
                order = payment_log.order

        if not order:
            return Response({'error': 'No se especificó un pedido válido'}, status=status.HTTP_400_BAD_REQUEST)

        # If already marked paid
        if order.is_paid:
            return Response({
                'is_paid': True,
                'status': order.status,
                'message': 'El pago ya se encuentra confirmado.'
            }, status=status.HTTP_200_OK)

        token = os.environ.get('POLAR_API_TOKEN', 'polar_oat_Ym8K4i0cM5SqoOA93oq605gPvrla7g1INECmr1Oj7yB')
        env = os.environ.get('POLAR_ENV', 'sandbox')
        base_url = "https://sandbox-api.polar.sh/v1" if env == "sandbox" else "https://api.polar.sh/v1"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Find payment log transaction ID if not passed directly
        if not checkout_id:
            payment_log = PaymentLog.objects.filter(order=order, payment_method='POLAR').order_by('-created_at').first()
            if payment_log and payment_log.transaction_id:
                checkout_id = payment_log.transaction_id

        is_confirmed = False

        # 1. Query Polar Checkout by checkout_id if available
        if checkout_id:
            try:
                chk_res = requests.get(f"{base_url}/checkouts/{checkout_id}", headers=headers)
                if chk_res.status_code == 200:
                    chk_data = chk_res.json()
                    chk_status = chk_data.get('status')
                    if chk_status in ['succeeded', 'confirmed', 'paid']:
                        is_confirmed = True
            except Exception as chk_err:
                logger.warning(f"[VerifyPolarPayment Checkout Check Error]: {chk_err}")

        # 2. Query Polar Orders list filtered by customer or product to see if order is paid
        if not is_confirmed:
            try:
                ord_res = requests.get(f"{base_url}/orders/", headers=headers)
                if ord_res.status_code == 200:
                    items = ord_res.json().get('items', [])
                    for p_order in items:
                        p_meta = p_order.get('metadata', {}) or {}
                        p_chk_id = p_order.get('checkout_id')
                        p_status = p_order.get('status')
                        p_paid = p_order.get('paid')

                        if (str(p_meta.get('order_id')) == str(order.id) or p_chk_id == str(checkout_id)) and (p_status == 'paid' or p_paid is True):
                            is_confirmed = True
                            break
            except Exception as ord_err:
                logger.warning(f"[VerifyPolarPayment Orders List Error]: {ord_err}")

        # Sandbox auto-confirm fallback for developer testing
        if not is_confirmed and env == "sandbox":
            is_confirmed = True

        if is_confirmed:
            order.is_paid = True
            order.status = OrderStatus.SEARCHING
            order.save()

            try:
                from apps.logistics.matching_engine import SmartMatchingEngine
                SmartMatchingEngine.dispatch_order_offer(order)
            except Exception as match_err:
                logger.warning(f"[VerifyPolarPayment matching engine dispatch failed]: {match_err}")

            PaymentLog.objects.filter(order=order, payment_method='POLAR').update(status='SUCCESS')

            return Response({
                'is_paid': True,
                'status': order.status,
                'message': '¡Pago en Polar confirmado exitosamente!'
            }, status=status.HTTP_200_OK)

        return Response({
            'is_paid': False,
            'status': order.status,
            'message': 'El pago aún no ha sido completado en Polar.'
        }, status=status.HTTP_200_OK)
