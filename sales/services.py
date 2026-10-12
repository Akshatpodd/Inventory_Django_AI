from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from inventory.services import post_movement

from .models import Sale, SaleLine

TWO_PLACES = Decimal('0.01')


def money(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@transaction.atomic
def create_sale(customer_name, customer_phone, discount, items, user, note=''):
    """items: list of (product, quantity, unit_price). Raises InsufficientStock / ValueError.

    Totals are calculated here, and every line posts a SALE movement to the stock ledger.
    """
    if not items:
        raise ValueError('Add at least one product.')
    discount = money(discount or 0)
    subtotal = tax_total = Decimal('0')
    for product, quantity, price in items:
        line = money(price) * quantity
        subtotal += line
        tax_total += money(line * product.tax_percent / 100)
    if discount < 0 or discount > subtotal + tax_total:
        raise ValueError('Discount cannot be negative or larger than the bill.')

    sale = Sale.objects.create(
        customer_name=customer_name.strip() or 'Walk-in customer', customer_phone=customer_phone or '',
        subtotal=money(subtotal), tax_total=money(tax_total), discount=discount,
        total=money(subtotal + tax_total - discount), created_by=user, note=note)
    for product, quantity, price in items:
        SaleLine.objects.create(sale=sale, product=product, quantity=quantity, unit_price=money(price),
                                unit_cost=product.cost_price, tax_percent=product.tax_percent)
        post_movement(product, 'SALE', quantity, user=user, reference=sale.number)
    return sale


@transaction.atomic
def cancel_sale(sale, user):
    """Whole-sale cancellation: puts all not-yet-returned units back into stock."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == 'CANCELLED':
        raise ValueError('This sale is already cancelled.')
    for line in sale.lines.select_related('product'):
        if line.returnable > 0:
            post_movement(line.product, 'RETURN_IN', line.returnable, user=user, reference=sale.number,
                          note='Sale cancelled')
            line.returned_qty = line.quantity
            line.save()
    sale.status = 'CANCELLED'
    sale.refunded_total = sale.total
    sale.save()


@transaction.atomic
def return_items(sale, quantities, user):
    """quantities: {line_id: units to return}. Refund = price + tax for those units (discount ignored)."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == 'CANCELLED':
        raise ValueError('This sale is cancelled.')
    refund = Decimal('0')
    any_returned = False
    for line in sale.lines.select_related('product'):
        qty = quantities.get(line.pk, 0)
        if qty < 0:
            raise ValueError('Return quantity cannot be negative.')
        if qty == 0:
            continue
        if qty > line.returnable:
            raise ValueError(f'{line.product.name}: only {line.returnable} unit(s) can be returned.')
        post_movement(line.product, 'RETURN_IN', qty, user=user, reference=sale.number, note='Customer return')
        line.returned_qty += qty
        line.save()
        refund += money(line.unit_price * qty * (1 + line.tax_percent / 100))
        any_returned = True
    if not any_returned:
        raise ValueError('Enter a return quantity for at least one product.')
    sale.refunded_total = min(sale.total, sale.refunded_total + refund)
    sale.save()
    return refund
