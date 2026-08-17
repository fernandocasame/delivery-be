from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, DriverProfile

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Platform Info', {'fields': ('phone_number', 'role', 'is_phone_verified', 'is_email_verified', 'profile_photo')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'phone_number', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_phone_verified')
    ordering = ('email',)


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'approval_status', 'status', 'vehicle_type', 'vehicle_plate', 'rating_avg', 'completed_orders_count')
    list_filter = ('approval_status', 'status', 'vehicle_type')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'vehicle_plate')
