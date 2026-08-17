from django.db import models
from django.conf import settings

class PushNotificationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    body = models.TextField()
    data_payload = models.JSONField(default=dict, blank=True)
    is_sent = models.BooleanField(default=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notificación -> {self.user.email}: {self.title}"
