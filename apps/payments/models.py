from django.db import models
from django.conf import settings

class DriverWallet(models.Model):
    driver = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pending_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet {self.driver.email}: ${self.balance}"


class TransactionType(models.TextChoices):
    DELIVERY_EARNING = 'DELIVERY_EARNING', 'Ganancia por entrega'
    PLATFORM_COMMISSION = 'PLATFORM_COMMISSION', 'Comisión plataforma'
    WITHDRAWAL = 'WITHDRAWAL', 'Retiro a cuenta bancaria'
    BONUS = 'BONUS', 'Bono por meta'
    PENALTY = 'PENALTY', 'Penalización'
    ORDER_PAYMENT = 'ORDER_PAYMENT', 'Pago de Pedido'
    REFUND = 'REFUND', 'Reembolso'


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(DriverWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.IntegerField(null=True, blank=True)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} ({self.wallet.driver.email})"


class WebhookLog(models.Model):
    event_type = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, default='POLAR')
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='PROCESSED')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider} - {self.event_type} ({self.status})"


class PaymentLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_logs')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_logs')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=30, default='SUCCESS')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(max_length=255)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PaymentLog #{self.id} | {self.payment_method} - ${self.amount} ({self.status})"


