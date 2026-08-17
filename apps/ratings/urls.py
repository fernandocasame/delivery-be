from django.urls import path
from .views import CreateRatingView

urlpatterns = [
    path('', CreateRatingView.as_view(), name='create_rating'),
]
