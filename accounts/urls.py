from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/', views.IMSLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/toggle/', views.UserToggleView.as_view(), name='user_toggle'),
    path('users/<int:pk>/password/', views.UserPasswordView.as_view(), name='user_password'),
]
