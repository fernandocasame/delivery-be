from django.urls import path
from .views import OrderListCreateView, OrderDetailView, OrderCancelView, CompleteDeliveryPODView, OrderAcceptView

urlpatterns = [
    path('', OrderListCreateView.as_view(), name='order_list_create'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('<int:pk>/accept/', OrderAcceptView.as_view(), name='order_accept'),
    path('<int:pk>/cancel/', OrderCancelView.as_view(), name='order_cancel'),
    path('<int:pk>/complete-pod/', CompleteDeliveryPODView.as_view(), name='order_complete_pod'),
]

