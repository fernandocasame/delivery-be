from django.db import models
from django.conf import settings

class DriverLocation(models.Model):
    driver = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='current_location')
    latitude = models.FloatField()
    longitude = models.FloatField()
    heading = models.FloatField(default=0.0) # Rotation angle in degrees
    speed = models.FloatField(default=0.0) # km/h
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ubicación {self.driver.email}: ({self.latitude}, {self.longitude})"


class OrderOffer(models.Model):
    class OfferStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        ACCEPTED = 'ACCEPTED', 'Aceptado'
        REJECTED = 'REJECTED', 'Rechazado'
        EXPIRED = 'EXPIRED', 'Expirado'

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='offers')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offers')
    status = models.CharField(max_length=20, choices=OfferStatus.choices, default=OfferStatus.PENDING)
    distance_km = models.FloatField()
    sequence = models.IntegerField()  # 0 for closest, 1 for second closest, etc.
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sequence']
        unique_together = ('order', 'driver')

    def __str__(self):
        return f"Offer {self.id} for Order #{self.order_id} to Driver {self.driver.email} ({self.status})"
