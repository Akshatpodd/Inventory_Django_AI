from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine


class LineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'supplier', 'status', 'order_date')
    inlines = [LineInline]
