from django.urls import path
from .views import UserNotificationListView

urlpatterns = [
    path('', UserNotificationListView.as_view(), name='notifications_list'),
]
