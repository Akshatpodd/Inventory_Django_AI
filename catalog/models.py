from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def with_stock(self):
        """Adds `.stock` = sum of all stock movements (the stock ledger)."""
        return self.annotate(stock=Coalesce(Sum('movements__delta'), 0))


class Product(models.Model):
    UNIT_CHOICES = [('PCS', 'Pieces'), ('KG', 'Kilogram'), ('G', 'Gram'), ('L', 'Litre'), ('ML', 'Millilitre'),
                    ('M', 'Metre'), ('BOX', 'Box'), ('PACK', 'Pack'), ('DOZEN', 'Dozen')]

    sku = models.CharField('SKU', max_length=40, unique=True, blank=True)
    barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='products')
    unit = models.CharField(max_length=6, choices=UNIT_CHOICES, default='PCS')
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField('Tax %', max_digits=5, decimal_places=2, default=0)
    reorder_point = models.PositiveIntegerField(default=0, help_text='Alert when stock falls to this level')
    min_order_qty = models.PositiveIntegerField('Minimum order quantity', default=1)
    pack_size = models.PositiveIntegerField(default=1, help_text='Orders are rounded up to whole packs')
    shelf_life_days = models.PositiveIntegerField(null=True, blank=True)
    preferred_supplier = models.ForeignKey('suppliers.Supplier', null=True, blank=True, on_delete=models.SET_NULL,
                                           related_name='preferred_products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.barcode:
            self.barcode = None          # many products without barcode must not clash on "unique"
        creating = self.pk is None
        if creating and not self.sku:
            self.sku = 'TMP'             # replaced below once we know the id
        super().save(*args, **kwargs)
        if creating and self.sku == 'TMP':
            self.sku = f'P{self.pk:06d}'
            super().save(update_fields=['sku'])

    @property
    def stock_on_hand(self):
        """Current stock = sum of the ledger."""
        return self.movements.aggregate(total=Coalesce(Sum('delta'), 0))['total']

    @property
    def margin_percent(self):
        if not self.selling_price:
            return None
        return round(float((self.selling_price - self.cost_price) / self.selling_price * 100), 1)

    def __str__(self):
        return f'{self.sku} - {self.name}'


class ProductSupplier(models.Model):
    """A supplier that sells a product, with its own price and lead time."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='supplier_links')
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.CASCADE, related_name='product_links')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    lead_time_days = models.PositiveSmallIntegerField(default=7)

    class Meta:
        unique_together = ('product', 'supplier')

    def __str__(self):
        return f'{self.product.name} from {self.supplier.name}'
