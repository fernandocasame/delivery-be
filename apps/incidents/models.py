from django.db import models
from django.conf import settings
from apps.orders.models import Order

class IncidentTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Abierto'
        IN_REVIEW = 'IN_REVIEW', 'En revisión'
        RESOLVED = 'RESOLVED', 'Resuelto'
        CLOSED = 'CLOSED', 'Cerrado'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='incidents')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Incidencia #{self.id} - {self.subject} [{self.status}]"
