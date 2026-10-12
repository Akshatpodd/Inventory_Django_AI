from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('APPROVED', 'Approved'), ('SENT', 'Sent'),
                      ('PARTIAL', 'Partly received'), ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled')]
    OPEN_STATUSES = ('APPROVED', 'SENT', 'PARTIAL')   # stock may still arrive

    number = models.CharField(max_length=20, unique=True, blank=True)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.PROTECT, related_name='purchase_orders')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    order_date = models.DateField(default=timezone.localdate)
    sent_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    first_received_date = models.DateField(null=True, blank=True)
    closed_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='purchase_orders_created')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='purchase_orders_approved')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-id']

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if creating and not self.number:
            self.number = 'TMP'
        super().save(*args, **kwargs)
        if creating and self.number == 'TMP':
            self.number = f'PO-{self.pk:06d}'
            super().save(update_fields=['number'])

    @property
    def total(self):
        return sum((line.line_total for line in self.lines.all()), Decimal('0'))

    @property
    def is_editable(self):
        return self.status == 'DRAFT'

    @property
    def lead_time_days(self):
        start = self.sent_date or self.order_date
        return (self.first_received_date - start).days if self.first_received_date else None

    def __str__(self):
        return self.number


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='purchase_lines')
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    received_qty = models.PositiveIntegerField(default=0)    # accepted into stock so far
    rejected_qty = models.PositiveIntegerField(default=0)    # delivered but refused (damaged)

    @property
    def line_total(self):
        return self.quantity * self.unit_cost

    @property
    def outstanding(self):
        return max(self.quantity - self.received_qty - self.rejected_qty, 0)

    def __str__(self):
        return f'{self.order.number}: {self.product.name} x {self.quantity}'
