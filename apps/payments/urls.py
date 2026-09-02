from django.urls import path
from .views import DriverWalletDetailView, PolarWebhookView, CreatePolarCheckoutView, VerifyPolarPaymentView

urlpatterns = [
    path('wallet/', DriverWalletDetailView.as_view(), name='driver_wallet'),
    path('polar-webhook/', PolarWebhookView.as_view(), name='polar_webhook'),
    path('create-polar-checkout/', CreatePolarCheckoutView.as_view(), name='create_polar_checkout'),
    path('verify-polar-payment/', VerifyPolarPaymentView.as_view(), name='verify_polar_payment'),
]


