from django.contrib import admin
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'driver', 'status', 'total_cost', 'vehicle_type', 'is_paid', 'created_at')
    list_filter = ('status', 'vehicle_type', 'is_paid', 'order_type')
    search_fields = ('client__email', 'driver__email', 'recipient_name', 'recipient_phone')
