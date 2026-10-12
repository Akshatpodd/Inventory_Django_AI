from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class Sale(models.Model):
    STATUS_CHOICES = [('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')]

    number = models.CharField(max_length=20, unique=True, blank=True)
    customer_name = models.CharField(max_length=150, default='Walk-in customer')
    customer_phone = models.CharField(max_length=10, blank=True,
                                      validators=[RegexValidator(r'^[6-9]\d{9}$', 'Enter a 10 digit mobile number.')])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='COMPLETED', db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunded_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='sales')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if creating and not self.number:
            self.number = 'TMP'
        super().save(*args, **kwargs)
        if creating and self.number == 'TMP':
            self.number = f'INV-{self.pk:06d}'
            super().save(update_fields=['number'])

    @property
    def net_total(self):
        return self.total - self.refunded_total

    def __str__(self):
        return self.number


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='sale_lines')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)   # cost at the time of sale (margin)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    returned_qty = models.PositiveIntegerField(default=0)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def returnable(self):
        return self.quantity - self.returned_qty

    def __str__(self):
        return f'{self.sale.number}: {self.product.name} x {self.quantity}'
