from django.test import TestCase

from accounts.models import User
from catalog.models import Product

from .models import StockMovement
from .services import InsufficientStock, post_movement


class LedgerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mgr', password='x', role='MANAGER')
        self.product = Product.objects.create(name='Rice', cost_price=40, selling_price=50)

    def test_stock_is_the_sum_of_the_ledger(self):
        post_movement(self.product, 'RECEIPT', 10, user=self.user)
        post_movement(self.product, 'SALE', 3, user=self.user)
        self.assertEqual(self.product.stock_on_hand, 7)
        self.assertEqual(Product.objects.with_stock().get(pk=self.product.pk).stock, 7)
        self.assertEqual(list(StockMovement.objects.order_by('id').values_list('delta', flat=True)), [10, -3])

    def test_cannot_sell_more_than_available(self):
        post_movement(self.product, 'RECEIPT', 5)
        with self.assertRaises(InsufficientStock):
            post_movement(self.product, 'SALE', 6)
        self.assertEqual(self.product.stock_on_hand, 5)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_quantity_must_be_positive(self):
        with self.assertRaises(ValueError):
            post_movement(self.product, 'RECEIPT', 0)

    def test_large_manual_adjustment_is_flagged_for_review(self):
        post_movement(self.product, 'RECEIPT', 100)
        small = post_movement(self.product, 'ADJUST_OUT', 5, reason_code='LOST')
        large = post_movement(self.product, 'ADJUST_OUT', 25, reason_code='LOST')
        self.assertFalse(small.needs_review)
        self.assertTrue(large.needs_review)

    def test_sku_is_generated(self):
        self.assertTrue(self.product.sku.startswith('P'))
        other = Product.objects.create(name='Dal')
        self.assertNotEqual(self.product.sku, other.sku)

    def test_blank_barcodes_do_not_clash(self):
        Product.objects.create(name='A', barcode='')
        Product.objects.create(name='B', barcode='')
