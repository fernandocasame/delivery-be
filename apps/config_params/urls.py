from django.urls import path
from .views import SystemParameterListCreateView, SystemParameterDetailView

urlpatterns = [
    path('', SystemParameterListCreateView.as_view(), name='config_list_create'),
    path('<str:key>/', SystemParameterDetailView.as_view(), name='config_detail'),
]
