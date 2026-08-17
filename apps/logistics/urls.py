from django.urls import path
from .views import ActiveFleetMapListView, UpdateLocationRESTView, DriverAcceptOrderView

urlpatterns = [
    path('fleet-map/', ActiveFleetMapListView.as_view(), name='fleet_map'),
    path('update-location/', UpdateLocationRESTView.as_view(), name='update_location_rest'),
    path('accept-order/<int:order_id>/', DriverAcceptOrderView.as_view(), name='driver_accept_order'),
]
