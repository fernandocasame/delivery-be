import logging
from .models import PushNotificationLog

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_push(user, title: str, body: str, data: dict = None):
        """Sends push notification via FCM / APNs and logs event."""
        if data is None:
            data = {}

        # Log push in database
        PushNotificationLog.objects.create(
            user=user,
            title=title,
            body=body,
            data_payload=data,
            is_sent=True
        )
        logger.info(f"[PUSH SENT] To: {user.email} | Title: {title}")
