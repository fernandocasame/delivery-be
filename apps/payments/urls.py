from django.urls import path
from .views import DriverWalletDetailView, PolarWebhookView

urlpatterns = [
    path('wallet/', DriverWalletDetailView.as_view(), name='driver_wallet'),
    path('polar-webhook/', PolarWebhookView.as_view(), name='polar_webhook'),
]

