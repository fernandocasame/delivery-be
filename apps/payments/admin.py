from django.contrib import admin
from .models import DriverWallet, WalletTransaction

@admin.register(DriverWallet)
class DriverWalletAdmin(admin.ModelAdmin):
    list_display = ('driver', 'balance', 'pending_payout', 'total_earned', 'updated_at')
    search_fields = ('driver__email',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'order_id', 'created_at')
    list_filter = ('transaction_type',)
