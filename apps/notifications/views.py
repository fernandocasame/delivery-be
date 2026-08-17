from rest_framework import generics, permissions, serializers
from .models import PushNotificationLog

class PushNotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushNotificationLog
        fields = '__all__'


class UserNotificationListView(generics.ListAPIView):
    serializer_class = PushNotificationLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PushNotificationLog.objects.filter(user=self.request.user).order_by('-sent_at')
