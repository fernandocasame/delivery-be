from django.urls import path
from .views import IncidentListCreateView

urlpatterns = [
    path('', IncidentListCreateView.as_view(), name='incidents_list_create'),
]
