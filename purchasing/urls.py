from django.urls import path

from . import views

app_name = 'purchasing'
urlpatterns = [
    path('', views.POListView.as_view(), name='list'),
    path('add/', views.POEditView.as_view(), name='create'),
    path('<int:pk>/', views.PODetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.POEditView.as_view(), name='edit'),
    path('<int:pk>/print/', views.POPrintView.as_view(), name='print'),
    path('<int:pk>/receive/', views.POReceiveView.as_view(), name='receive'),
    path('<int:pk>/<str:action>/', views.POActionView.as_view(), name='action'),
]
