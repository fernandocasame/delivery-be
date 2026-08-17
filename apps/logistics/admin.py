from django.contrib import admin
from .models import DriverLocation

@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ('driver', 'latitude', 'longitude', 'heading', 'speed', 'updated_at')
    search_fields = ('driver__email',)
