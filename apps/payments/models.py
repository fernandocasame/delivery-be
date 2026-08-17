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


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(DriverWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.IntegerField(null=True, blank=True)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} ({self.wallet.driver.email})"
