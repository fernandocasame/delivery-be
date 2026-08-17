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
