from django.urls import path
from .views import DriverWalletDetailView

urlpatterns = [
    path('wallet/', DriverWalletDetailView.as_view(), name='driver_wallet'),
]
