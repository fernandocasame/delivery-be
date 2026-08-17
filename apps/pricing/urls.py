from django.urls import path
from .views import VehicleTariffListView, VehicleTariffDetailView, EstimatePriceView

urlpatterns = [
    path('tariffs/', VehicleTariffListView.as_view(), name='tariff_list'),
    path('tariffs/<int:pk>/', VehicleTariffDetailView.as_view(), name='tariff_detail'),
    path('estimate/', EstimatePriceView.as_view(), name='estimate_price'),
]
