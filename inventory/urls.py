from django.urls import path

from . import views

app_name = 'inventory'
urlpatterns = [
    path('', views.MovementListView.as_view(), name='movements'),
    path('adjust/', views.AdjustmentView.as_view(), name='adjust'),
    path('stocktake/', views.StockTakeView.as_view(), name='stocktake'),
]
