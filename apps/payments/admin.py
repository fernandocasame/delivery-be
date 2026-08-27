from django.contrib import admin
from .models import DriverWallet, WalletTransaction, WebhookLog, PaymentLog

@admin.register(DriverWallet)
class DriverWalletAdmin(admin.ModelAdmin):
    list_display = ('driver', 'balance', 'pending_payout', 'total_earned', 'updated_at')
    search_fields = ('driver__email',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'order_id', 'created_at')
    list_filter = ('transaction_type',)


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider', 'event_type', 'status', 'created_at')
    list_filter = ('provider', 'status', 'event_type')
    search_fields = ('event_type', 'provider', 'error_message')


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('payment_method', 'status')
    search_fields = ('user__email', 'order__id', 'description', 'transaction_id')


