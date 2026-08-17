from django.contrib import admin
from .models import IncidentTicket

@admin.register(IncidentTicket)
class IncidentTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'order', 'reported_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject', 'description', 'reported_by__email')
