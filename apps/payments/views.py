import os
import json
import logging
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import DriverWallet, WalletTransaction, TransactionType, WebhookLog
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
            if isinstance(data, dict):
                customer_email = data.get('customer_email') or data.get('user', {}).get('email')
                amount_cents = data.get('amount') or data.get('net_amount') or 0
            else:
                customer_email = getattr(data, 'customer_email', None)
                amount_cents = getattr(data, 'amount', 0)

            amount = float(amount_cents) / 100.0 if isinstance(amount_cents, int) and amount_cents > 100 else float(amount_cents or 0)

            if customer_email:
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

                        from .models import PaymentLog
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



