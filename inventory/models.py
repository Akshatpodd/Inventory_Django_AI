from django.conf import settings
from django.db import models
from django.utils import timezone

# movement type -> direction (+1 adds stock, -1 removes stock)
DIRECTION = {
    'OPENING': 1, 'RECEIPT': 1, 'RETURN_IN': 1, 'ADJUST_IN': 1,
    'SALE': -1, 'ADJUST_OUT': -1, 'DAMAGE': -1, 'RETURN_OUT': -1,
}


class StockMovement(models.Model):
    """One line of the stock ledger. Stock on hand is the SUM of `delta`; it is never edited directly."""
    TYPE_CHOICES = [
        ('OPENING', 'Opening balance'), ('RECEIPT', 'Goods receipt'), ('SALE', 'Sale'),
        ('RETURN_IN', 'Customer return'), ('RETURN_OUT', 'Return to supplier'),
        ('ADJUST_IN', 'Adjustment (add)'), ('ADJUST_OUT', 'Adjustment (remove)'), ('DAMAGE', 'Damaged / expired'),
    ]
    REASON_CHOICES = [('COUNT', 'Stock-take correction'), ('DAMAGED', 'Damaged'), ('EXPIRED', 'Expired'),
                      ('LOST', 'Lost / theft'), ('FOUND', 'Found'), ('OTHER', 'Other')]

    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=12, choices=TYPE_CHOICES, db_index=True)
    delta = models.IntegerField(help_text='Positive adds stock, negative removes it')
    reason_code = models.CharField(max_length=10, choices=REASON_CHOICES, blank=True)
    note = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=60, blank=True, help_text='For example INV-000012 or PO-000004')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='stock_movements')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    needs_review = models.BooleanField(default=False, help_text='Large manual adjustment waiting for a manager')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='reviewed_movements')

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['product', 'created_at'])]

    def __str__(self):
        return f'{self.get_movement_type_display()} {self.delta:+d} x {self.product_id}'
