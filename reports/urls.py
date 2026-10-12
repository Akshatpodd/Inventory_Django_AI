from django.urls import path

from . import views

app_name = 'reports'
urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('reports/', views.ReportIndexView.as_view(), name='index'),
] + [path(f'reports/{r.slug}/', r.as_view(), name=r.slug) for r in views.REPORTS]
