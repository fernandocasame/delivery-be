from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # OpenAPI Schema & Swagger UI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # API v1 endpoints
    path('api/v1/users/', include('apps.users.urls')),
    path('api/v1/config/', include('apps.config_params.urls')),
    path('api/v1/pricing/', include('apps.pricing.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/logistics/', include('apps.logistics.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/ratings/', include('apps.ratings.urls')),
    path('api/v1/incidents/', include('apps.incidents.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
