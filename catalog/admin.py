from django.contrib import admin

from .models import Category, Product, ProductSupplier

admin.site.register(Category)
admin.site.register(ProductSupplier)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'category', 'selling_price', 'is_active')
    search_fields = ('sku', 'name', 'barcode')
