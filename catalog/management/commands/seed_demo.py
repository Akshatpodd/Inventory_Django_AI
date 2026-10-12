"""Fill the database with demo data so every screen has something to show.

    python manage.py seed_demo            # users, products, 150 days of sales and purchase history
    python manage.py seed_demo --force    # add the data even if products already exist

The data is random (but repeatable with --seed). It is for demos and testing only.
"""
import math
import random
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import Category, Product, ProductSupplier
from inventory.models import StockMovement
from purchasing.models import PurchaseOrder, PurchaseOrderLine
from sales.models import Sale, SaleLine
from sales.services import money
from suppliers.models import Supplier

User = get_user_model()

SUPPLIERS = [
    # name, promised lead days, extra delay (min, max), reject rate, price factor
    ('Sharma Wholesale Traders', 3, (0, 0), 0.00, 1.00),
    ('Metro Distribution Co', 5, (0, 3), 0.01, 0.97),
    ('Budget Bazaar Suppliers', 6, (0, 7), 0.05, 0.92),
]
# name, category, cost, price, base units/day, supplier index, pack size, min order qty, tax %
PRODUCTS = [
    ('Basmati Rice 5kg', 'Grocery', 420, 520, 9, 0, 4, 8, 5), ('Toor Dal 1kg', 'Grocery', 118, 148, 11, 0, 10, 20, 5),
    ('Sunflower Oil 1L', 'Grocery', 128, 155, 12, 1, 12, 24, 5), ('Sugar 1kg', 'Grocery', 41, 52, 14, 0, 10, 20, 5),
    ('Tea Leaves 250g', 'Grocery', 82, 110, 8, 1, 10, 20, 5), ('Cream Biscuits Pack', 'Snacks', 18, 25, 22, 2, 24, 48, 12),
    ('Instant Noodles 4-pack', 'Snacks', 48, 64, 16, 1, 12, 24, 12), ('Potato Chips 90g', 'Snacks', 17, 25, 18, 2, 24, 48, 12),
    ('Bath Soap 100g', 'Personal Care', 28, 40, 15, 1, 12, 24, 18), ('Shampoo 200ml', 'Personal Care', 92, 135, 6, 1, 6, 12, 18),
    ('Toothpaste 150g', 'Personal Care', 64, 88, 10, 0, 12, 24, 18), ('Hand Sanitizer 100ml', 'Personal Care', 36, 60, 5, 2, 12, 24, 18),
    ('Detergent Powder 1kg', 'Household', 88, 118, 8, 0, 10, 20, 18), ('Dish Wash Gel 500ml', 'Household', 72, 99, 6, 1, 12, 12, 18),
    ('LED Bulb 9W', 'Household', 58, 95, 4, 2, 10, 20, 12), ('AA Batteries 4-pack', 'Household', 70, 110, 3, 2, 10, 10, 18),
    ('Notebook A5', 'Stationery', 24, 40, 13, 1, 20, 40, 12), ('Ball Pen Box (10)', 'Stationery', 38, 60, 7, 2, 10, 20, 12),
    ('A4 Paper Ream', 'Stationery', 205, 260, 3, 0, 5, 10, 12), ('Glue Stick', 'Stationery', 14, 25, 5, 2, 20, 40, 12),
    ('Steel Water Bottle 1L', 'Home', 210, 350, 2, 1, 4, 8, 18), ('Phone Charging Cable', 'Electronics', 62, 149, 4, 2, 10, 20, 18),
    ('Earphones Wired', 'Electronics', 95, 199, 3, 2, 10, 10, 18), ('Premium Saffron 1g', 'Grocery', 160, 260, 0.25, 1, 5, 10, 5),
    ('Wall Calendar 2025', 'Stationery', 35, 70, 2, 2, 10, 20, 12),
]
WEEKDAY = [0.90, 0.90, 0.95, 1.00, 1.20, 1.50, 1.40]     # Monday ... Sunday
HOLIDAYS = [(8, 15, 'Independence Day'), (10, 2, 'Gandhi Jayanti'), (1, 26, 'Republic Day'), (12, 25, 'Christmas')]


def poisson(rng, mean):
    """Small random count with the given average (Knuth's method)."""
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def binomial(rng, n, chance):
    return sum(1 for _ in range(n) if rng.random() < chance)


def aware(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, dtime(hour, minute)))


class Command(BaseCommand):
    help = 'Create demo users, products and 150 days of sales / purchase history.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=150)
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--password', default='ChangeMe123!', help='Password for the demo users')
        parser.add_argument('--force', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        if Product.objects.exists() and not opts['force']:
            raise CommandError('Products already exist. Use --force to add demo data anyway.')
        rng = random.Random(opts['seed'])
        days = opts['days']
        end = timezone.localdate() - timedelta(days=1)
        start = end - timedelta(days=days - 1)

        users = self._users(opts['password'])
        suppliers = [Supplier.objects.get_or_create(name=n, defaults=dict(
            default_lead_time_days=lead, contact_person='Demo contact', phone='9876500000', payment_terms='Net 30'))[0]
            for n, lead, *_ in SUPPLIERS]
        holidays = self._holidays(start, end)

        categories, products = {}, []
        for name, cat, cost, price, base, sidx, pack, moq, tax in PRODUCTS:
            category = categories.setdefault(cat, Category.objects.get_or_create(name=cat)[0])
            p = Product.objects.create(
                name=name, category=category, cost_price=cost, selling_price=price, tax_percent=tax,
                pack_size=pack, min_order_qty=moq, preferred_supplier=suppliers[sidx],
                reorder_point=int(math.ceil(base * 7)))
            ProductSupplier.objects.create(product=p, supplier=suppliers[sidx], unit_cost=cost,
                                           lead_time_days=SUPPLIERS[sidx][1])
            other = (sidx + 1) % 3
            if base >= 5:     # a second supplier for fast sellers, so price comparison has data
                ProductSupplier.objects.create(product=p, supplier=suppliers[other],
                                               unit_cost=Decimal(str(round(cost * 1.06, 2))),
                                               lead_time_days=SUPPLIERS[other][1])
            products.append((p, base, sidx, pack, moq))

        movements, sales_by_day, po_events, end_stock = [], {}, [], {}
        for p, base, sidx, pack, moq in products:
            stock, pending, on_order = 0, [], 0
            initial = int(base * (360 if 'Saffron' in p.name else 18)) + (120 if 'Calendar' in p.name else 0)
            stock = max(initial, 5)
            movements.append(StockMovement(product=p, movement_type='OPENING', delta=stock, reference='Opening balance',
                                           created_at=aware(start - timedelta(days=1), 8), note='Demo opening stock'))
            _, promised, (dmin, dmax), reject_rate, _ = SUPPLIERS[sidx]
            reorder_level = int(math.ceil(base * (promised + 2)))
            order_qty = max(int(math.ceil(base * 21 / pack) * pack), moq)
            for t in range(days):
                day = start + timedelta(days=t)
                for event in [e for e in pending if e['arrival'] == day]:
                    pending.remove(event)
                    on_order -= event['qty']
                    event['received'] = event['qty'] - event['rejected']
                    stock += event['received']
                    if event['received']:
                        movements.append(StockMovement(
                            product=p, movement_type='RECEIPT', delta=event['received'], reference='PO',
                            created_at=aware(day, 11), note='Goods receipt'))
                        event['movement'] = movements[-1]
                mean = base * WEEKDAY[day.weekday()] * (1 + 0.002 * t)
                if day in holidays:
                    mean *= 1.6 if holidays[day] != 'Salary day' else 1.3
                if 'Calendar' in p.name and t > 25:
                    mean = 0.0
                sold = min(poisson(rng, mean), stock) if mean > 0 else 0
                if sold:
                    stock -= sold
                    sales_by_day.setdefault(day, []).append((p, sold))
                if stock + on_order <= reorder_level and on_order == 0 and 'Calendar' not in p.name \
                        and 'Saffron' not in p.name:
                    delay = rng.randint(dmin, dmax) if dmax else 0
                    arrival = day + timedelta(days=promised + delay)
                    rejected = binomial(rng, order_qty, reject_rate) if reject_rate else 0
                    event = dict(product=p, sidx=sidx, sent=day, promised=day + timedelta(days=promised),
                                 arrival=arrival, qty=order_qty, rejected=rejected, received=0)
                    po_events.append(event)
                    pending.append(event)
                    on_order += order_qty
            end_stock[p.pk] = stock

        # purchase orders (history + a few still open) --------------------------------
        manager = users['manager']
        for event in po_events:
            arrived = event['arrival'] <= end
            sup = suppliers[event['sidx']]
            po = PurchaseOrder.objects.create(
                supplier=sup, status='CLOSED' if arrived else 'SENT', order_date=event['sent'], sent_date=event['sent'],
                expected_date=event['promised'], first_received_date=event['arrival'] if arrived else None,
                closed_date=event['arrival'] if arrived else None, created_by=manager, approved_by=manager,
                created_at=aware(event['sent'], 9), note='Demo order')
            unit_cost = money(Decimal(str(event['product'].cost_price)) * Decimal(str(SUPPLIERS[event['sidx']][4])))
            PurchaseOrderLine.objects.create(
                order=po, product=event['product'], quantity=event['qty'], unit_cost=unit_cost,
                received_qty=event['received'] if arrived else 0, rejected_qty=event['rejected'] if arrived else 0)
            if event.get('movement') and arrived:
                event['movement'].reference = po.number
        movements = [m for m in movements if not (m.movement_type == 'RECEIPT' and m.created_at.date() > end)]

        # daily sales -----------------------------------------------------------------
        seller = users['sales']
        for day in sorted(sales_by_day):
            lines = sales_by_day[day]
            subtotal = sum(money(p.selling_price) * q for p, q in lines)
            tax = sum(money(money(p.selling_price) * q * p.tax_percent / 100) for p, q in lines)
            sale = Sale.objects.create(
                customer_name='Daily counter sales', subtotal=money(subtotal), tax_total=money(tax),
                total=money(subtotal + tax), created_by=seller, created_at=aware(day, rng.randint(9, 20),
                                                                                  rng.randint(0, 59)))
            SaleLine.objects.bulk_create([SaleLine(sale=sale, product=p, quantity=q, unit_price=p.selling_price,
                                                   unit_cost=p.cost_price, tax_percent=p.tax_percent) for p, q in lines])
            movements += [StockMovement(product=p, movement_type='SALE', delta=-q, reference=sale.number, user=seller,
                                        created_at=sale.created_at) for p, q in lines]
        self._write_off(users, products, end_stock, end, movements)
        StockMovement.objects.bulk_create(movements, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f'Demo data created: {len(products)} products, {len(sales_by_day)} sales days, {len(po_events)} purchase orders.'))
        self.stdout.write(f"Users (password '{opts['password']}'): admin, manager, sales, viewer")

    def _users(self, password):
        users = {}
        for username, role, first in [('admin', 'ADMIN', 'Asha'), ('manager', 'MANAGER', 'Manoj'),
                                      ('sales', 'SALES', 'Sana'), ('viewer', 'VIEWER', 'Vikram')]:
            user, created = User.objects.get_or_create(username=username, defaults=dict(
                role=role, first_name=first, email=f'{username}@example.com', is_staff=(role == 'ADMIN'),
                is_superuser=(role == 'ADMIN')))
            if created:
                user.set_password(password)
                user.save()
            users[username] = user
        return users

    def _holidays(self, start, end):
        """Fixed holidays plus the 1st of every month (salary day), as {date: name}. Used to lift demand."""
        found = {}
        for month, day_no, name in HOLIDAYS:
            for year in (start.year, end.year):
                try:
                    d = date(year, month, day_no)
                except ValueError:
                    continue
                if start <= d <= end:
                    found[d] = name
        d = date(start.year, start.month, 1)
        while d <= end:
            if d >= start:
                found.setdefault(d, 'Salary day')
            d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        return found

    def _write_off(self, users, products, end_stock, end, movements):
        """One large write-off, so the 'needs review' flag on the stock ledger has something to show."""
        biggest = max(products, key=lambda row: end_stock[row[0].pk])[0]
        movements.append(StockMovement(product=biggest, movement_type='ADJUST_OUT', delta=-30, reason_code='LOST',
                                       note='Demo: write-off', reference='Manual adjustment', user=users['manager'],
                                       needs_review=True, created_at=aware(end, 17, 40)))
