from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Product
from suppliers.models import Supplier

from . import services
from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mgr', password='x', role='MANAGER')
        self.supplier = Supplier.objects.create(name='Acme', default_lead_time_days=4)
        self.product = Product.objects.create(name='Flour', cost_price=20, selling_price=30, preferred_supplier=self.supplier)
        self.po = PurchaseOrder.objects.create(supplier=self.supplier, created_by=self.user)
        self.line = PurchaseOrderLine.objects.create(order=self.po, product=self.product, quantity=100, unit_cost=20)

    def test_workflow_and_goods_receipt(self):
        services.approve(self.po, self.user)
        services.mark_sent(self.po)
        self.assertEqual(self.po.expected_date, timezone.localdate() + timedelta(days=4))
        services.receive_goods(self.po, {self.line.pk: (60, 5)}, self.user)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'PARTIAL')
        self.assertEqual(self.product.stock_on_hand, 60)          # rejected units never enter stock
        services.receive_goods(self.po, {self.line.pk: (35, 0)}, self.user)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'CLOSED')
        self.assertEqual(self.product.stock_on_hand, 95)
        self.assertEqual(self.po.lead_time_days, 0)

    def test_cannot_receive_more_than_expected(self):
        services.approve(self.po, self.user)
        with self.assertRaises(ValueError):
            services.receive_goods(self.po, {self.line.pk: (101, 0)}, self.user)
        self.assertEqual(self.product.stock_on_hand, 0)

    def test_empty_order_cannot_be_approved(self):
        empty = PurchaseOrder.objects.create(supplier=self.supplier)
        with self.assertRaises(ValueError):
            services.approve(empty, self.user)
