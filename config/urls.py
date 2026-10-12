from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('catalog/', include('catalog.urls')),
    path('inventory/', include('inventory.urls')),
    path('purchasing/', include('purchasing.urls')),
    path('sales/', include('sales.urls')),
    path('audit/', include('audit.urls')),
    path('api/', include('config.api_urls')),
    path('', include('reports.urls')),
]
