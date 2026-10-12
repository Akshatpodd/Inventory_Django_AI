from django.urls import path

from . import views

app_name = 'catalog'
urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/add/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/import/', views.ProductImportView.as_view(), name='product_import'),
    path('products/export/', views.ProductExportView.as_view(), name='product_export'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/<int:pk>/toggle/', views.ProductToggleView.as_view(), name='product_toggle'),
    path('products/<int:product_pk>/suppliers/add/', views.ProductSupplierAddView.as_view(), name='supplier_add'),
    path('supplier-links/<int:pk>/remove/', views.ProductSupplierRemoveView.as_view(), name='supplier_remove'),
]
