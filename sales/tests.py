from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Product
from inventory.services import InsufficientStock, post_movement

from . import services
from .models import Sale


class SaleServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cashier', password='x', role='SALES')
        self.product = Product.objects.create(name='Soap', cost_price=30, selling_price=100, tax_percent=18)
        post_movement(self.product, 'RECEIPT', 20)

    def test_totals_tax_discount_and_stock(self):
        sale = services.create_sale('Ravi', '9876543210', Decimal('10'), [(self.product, 2, Decimal('100'))], self.user)
        self.assertEqual(sale.subtotal, Decimal('200.00'))
        self.assertEqual(sale.tax_total, Decimal('36.00'))
        self.assertEqual(sale.total, Decimal('226.00'))
        self.assertEqual(self.product.stock_on_hand, 18)
        self.assertTrue(sale.number.startswith('INV-'))

    def test_not_enough_stock_creates_nothing(self):
        with self.assertRaises(InsufficientStock):
            services.create_sale('', '', 0, [(self.product, 21, Decimal('100'))], self.user)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(self.product.stock_on_hand, 20)

    def test_discount_cannot_exceed_bill(self):
        with self.assertRaises(ValueError):
            services.create_sale('', '', Decimal('500'), [(self.product, 1, Decimal('100'))], self.user)

    def test_cancel_puts_stock_back(self):
        sale = services.create_sale('', '', 0, [(self.product, 5, Decimal('100'))], self.user)
        services.cancel_sale(sale, self.user)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'CANCELLED')
        self.assertEqual(self.product.stock_on_hand, 20)
        with self.assertRaises(ValueError):
            services.cancel_sale(sale, self.user)

    def test_partial_return_refunds_price_plus_tax(self):
        sale = services.create_sale('', '', 0, [(self.product, 4, Decimal('100'))], self.user)
        line = sale.lines.get()
        refund = services.return_items(sale, {line.pk: 1}, self.user)
        self.assertEqual(refund, Decimal('118.00'))
        self.assertEqual(self.product.stock_on_hand, 17)
        with self.assertRaises(ValueError):
            services.return_items(sale, {line.pk: 4}, self.user)    # only 3 left to return


class SaleViewTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('s', password='pw12345!', role='SALES')
        self.viewer = User.objects.create_user('v', password='pw12345!', role='VIEWER')
        self.product = Product.objects.create(name='Pen', cost_price=5, selling_price=10)
        post_movement(self.product, 'RECEIPT', 50)

    def test_seller_can_create_sale_from_the_form(self):
        self.client.force_login(self.seller)
        data = {'customer_name': 'Walk-in', 'customer_phone': '', 'discount': '0', 'note': '',
                'form-TOTAL_FORMS': '2', 'form-INITIAL_FORMS': '0', 'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
                'form-0-product': self.product.pk, 'form-0-quantity': '3', 'form-0-unit_price': '',
                'form-1-product': '', 'form-1-quantity': '', 'form-1-unit_price': ''}
        response = self.client.post(reverse('sales:create'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.get().total, Decimal('30.00'))
        self.assertEqual(self.product.stock_on_hand, 47)

    def test_viewer_cannot_create_sales(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('sales:create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('sales:list')).status_code, 200)
