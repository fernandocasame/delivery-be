from django.contrib import admin
from .models import PushNotificationLog

@admin.register(PushNotificationLog)
class PushNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_sent', 'sent_at')
    search_fields = ('user__email', 'title', 'body')
