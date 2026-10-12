"""One-time import from the old Tkinter + MySQL Inventory Management System.

    python manage.py import_legacy --host localhost --user root --password 1234 --database inventory_system

What happens
  * Employees become users. Old plain-text passwords are NOT copied: use --default-password or reset them on the Users screen.
  * Suppliers, categories and products are copied. The old app had no cost price, so cost = selling price
    (correct it afterwards, margins depend on it).
  * Old sales (with their JSON items) become sales and SALE movements with their original dates.
  * Current stock becomes an OPENING balance, adjusted so the ledger ends at the old stock level.
"""
import json
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import Category, Product
from inventory.models import StockMovement
from sales.models import Sale, SaleLine
from sales.services import money
from suppliers.models import Supplier

User = get_user_model()


class Command(BaseCommand):
    help = 'Import employees, suppliers, categories, products and sales from the old MySQL inventory_system database.'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='localhost')
        parser.add_argument('--port', type=int, default=3306)
        parser.add_argument('--user', default='root')
        parser.add_argument('--password', default='1234')
        parser.add_argument('--database', default='inventory_system')
        parser.add_argument('--default-password', default='', help='Password given to every imported user')
        parser.add_argument('--force', action='store_true', help='Import even if products already exist')

    def handle(self, *args, **opts):
        import pymysql
        if Product.objects.exists() and not opts['force']:
            raise CommandError('The new database already has products. Use --force to import anyway.')
        try:
            conn = pymysql.connect(host=opts['host'], port=opts['port'], user=opts['user'], password=opts['password'],
                                   database=opts['database'], charset='utf8mb4',
                                   cursorclass=pymysql.cursors.DictCursor)
        except pymysql.MySQLError as exc:
            raise CommandError(f'Cannot connect to the old database: {exc}')
        with conn, conn.cursor() as cur:
            def fetch(table):
                try:
                    cur.execute(f'SELECT * FROM {table}')
                    return cur.fetchall()
                except pymysql.MySQLError:
                    self.stdout.write(self.style.WARNING(f'Table {table} not found: skipped.'))
                    return []
            employees, suppliers = fetch('employee_data'), fetch('supplier_data')
            categories, products, sales = fetch('category_data'), fetch('product_data'), fetch('sales_data')
        with transaction.atomic():
            self._import(employees, suppliers, categories, products, sales, opts['default_password'])

    def _import(self, employees, suppliers, categories, products, sales, default_password):
        # ---- users
        for row in employees:
            username = str(row['empid'])
            if User.objects.filter(username=username).exists():
                continue
            parts = (row.get('name') or '').split(' ', 1)
            user = User(username=username, first_name=parts[0][:150], last_name=(parts[1] if len(parts) > 1 else '')[:150],
                        email=row.get('email') or '', phone=(row.get('contact') or '')[:15],
                        role='ADMIN' if row.get('usertype') == 'Admin' else 'SALES')
            if default_password:
                user.set_password(default_password)
            else:
                user.set_unusable_password()
            user.save()
        # ---- suppliers, categories
        supplier_by_name = {}
        for row in suppliers:
            obj, _ = Supplier.objects.get_or_create(name=row['name'], defaults=dict(
                phone=(row.get('contact') or '')[:20], address=f"Imported note: {row.get('description') or ''}".strip()))
            supplier_by_name[row['name']] = obj
        category_by_name = {}
        for row in categories:
            obj, _ = Category.objects.get_or_create(name=row['name'], defaults=dict(description=row.get('description') or ''))
            category_by_name[row['name']] = obj
        # ---- products
        product_by_legacy_id, product_by_name, legacy_stock = {}, {}, {}
        for row in products:
            category = category_by_name.get(row.get('category')) or (
                Category.objects.get_or_create(name=row['category'])[0] if row.get('category') else None)
            supplier = supplier_by_name.get(row.get('supplier')) or (
                supplier_by_name.setdefault(row['supplier'], Supplier.objects.get_or_create(name=row['supplier'])[0])
                if row.get('supplier') else None)
            name = row['name']
            if Product.objects.filter(name=name).exists():
                name = f"{name} ({row.get('supplier') or row['id']})"
            price = Decimal(str(row.get('price') or 0))
            product = Product.objects.create(name=name, category=category, preferred_supplier=supplier,
                                             cost_price=price, selling_price=price,
                                             is_active=(row.get('status') == 'Active'))
            product_by_legacy_id[row['id']] = product
            product_by_name[row['name']] = product
            legacy_stock[product.pk] = int(row.get('quantity') or 0)
        # ---- sales and their stock movements
        sold = defaultdict(int)
        first_sale = {}
        movements = []
        for row in sorted(sales, key=lambda r: r['date_time']):
            items = row['items']
            items = json.loads(items) if isinstance(items, (str, bytes)) else items
            when = timezone.make_aware(row['date_time']) if timezone.is_naive(row['date_time']) else row['date_time']
            phone = row.get('contact_no') or ''
            total = money(row['total'])
            sale = Sale.objects.create(customer_name=row.get('customer_name') or 'Walk-in customer',
                                       customer_phone=phone if re.fullmatch(r'[6-9]\d{9}', phone) else '',
                                       subtotal=total, total=total, created_at=when, note='Imported from old system')
            for item in items:
                product = product_by_legacy_id.get(item.get('id')) or product_by_name.get(item.get('product'))
                if product is None:
                    self.stdout.write(self.style.WARNING(f"Sale {row['id']}: product {item.get('product')} not found."))
                    continue
                qty = int(item['quantity'])
                SaleLine.objects.create(sale=sale, product=product, quantity=qty, unit_price=money(item['price']),
                                        unit_cost=product.cost_price)
                movements.append(StockMovement(product=product, movement_type='SALE', delta=-qty,
                                               reference=sale.number, created_at=when))
                sold[product.pk] += qty
                first_sale.setdefault(product.pk, when)
        # ---- opening balances so that the ledger ends at the old stock level
        for product in product_by_legacy_id.values():
            opening = legacy_stock[product.pk] + sold[product.pk]
            if opening > 0:
                when = (first_sale.get(product.pk) or timezone.now()) - timedelta(minutes=1)
                movements.append(StockMovement(product=product, movement_type='OPENING', delta=opening,
                                               reference='Imported opening balance', created_at=when))
        StockMovement.objects.bulk_create(movements, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(employees)} users, {len(suppliers)} suppliers, {len(categories)} categories, '
            f'{len(products)} products, {len(sales)} sales.'))
        if not default_password:
            self.stdout.write(self.style.WARNING('Users have no password yet: set one on the Users screen.'))
        self.stdout.write(self.style.WARNING('Cost price was set equal to selling price. Please correct it.'))
