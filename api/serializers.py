from rest_framework import serializers

from catalog.models import Product
from purchasing.models import PurchaseOrder, PurchaseOrderLine
from sales.models import Sale, SaleLine


class ProductSerializer(serializers.ModelSerializer):
    stock = serializers.IntegerField(read_only=True)
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = ['id', 'sku', 'barcode', 'name', 'category', 'unit', 'cost_price', 'selling_price', 'tax_percent',
                  'reorder_point', 'min_order_qty', 'pack_size', 'is_active', 'stock']


class SaleLineSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()

    class Meta:
        model = SaleLine
        fields = ['product', 'quantity', 'unit_price', 'tax_percent', 'returned_qty']


class SaleSerializer(serializers.ModelSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ['id', 'number', 'customer_name', 'status', 'subtotal', 'tax_total', 'discount', 'total',
                  'refunded_total', 'created_at', 'lines']


class POLineSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()

    class Meta:
        model = PurchaseOrderLine
        fields = ['product', 'quantity', 'unit_cost', 'received_qty', 'rejected_qty']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier = serializers.StringRelatedField()
    lines = POLineSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'number', 'supplier', 'status', 'order_date', 'expected_date', 'first_received_date', 'lines']

