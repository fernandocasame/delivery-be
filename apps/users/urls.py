from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView, UserProfileView, DriverDocumentUploadView,
    DriverStatusToggleView, DriverListView, DriverApprovalView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserProfileView.as_view(), name='user_profile'),
    path('driver/documents/', DriverDocumentUploadView.as_view(), name='driver_documents'),
    path('driver/status/', DriverStatusToggleView.as_view(), name='driver_status_toggle'),
    path('admin/drivers/', DriverListView.as_view(), name='admin_drivers_list'),
    path('admin/drivers/<int:pk>/approval/', DriverApprovalView.as_view(), name='admin_driver_approval'),
]
