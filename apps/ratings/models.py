from django.db import models
from django.conf import settings
from apps.orders.models import Order

class OrderRating(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='ratings')
    rated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_ratings')
    rated_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_ratings')

    punctuality_score = models.IntegerField(default=5)
    friendliness_score = models.IntegerField(default=5)
    package_condition_score = models.IntegerField(default=5)
    overall_score = models.IntegerField(default=5)

    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'rated_by')

    def __str__(self):
        return f"Rating para {self.rated_user.email}: {self.overall_score}⭐"
