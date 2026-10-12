from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from api import views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='api-product')
router.register('sales', views.SaleViewSet, basename='api-sale')
router.register('purchase-orders', views.PurchaseOrderViewSet, basename='api-po')

urlpatterns = [
    path('token/', obtain_auth_token, name='api-token'),
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    path('', include(router.urls)),
]
