from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from catalog.models import ProductSupplier
from inventory.services import post_movement

from .models import PurchaseOrder, PurchaseOrderLine


def supplier_for_product(product):
    """Preferred supplier, otherwise the cheapest linked supplier. Returns (supplier, unit_cost, lead_days)."""
    if product.preferred_supplier_id:
        link = ProductSupplier.objects.filter(product=product, supplier=product.preferred_supplier).first()
        cost = link.unit_cost if link else product.cost_price
        lead = link.lead_time_days if link else product.preferred_supplier.default_lead_time_days
        return product.preferred_supplier, cost, lead
    link = ProductSupplier.objects.filter(product=product).select_related('supplier').order_by('unit_cost').first()
    if link:
        return link.supplier, link.unit_cost, link.lead_time_days
    return None, product.cost_price, None


def approve(po, user):
    if po.status != 'DRAFT':
        raise ValueError('Only draft orders can be approved.')
    if not po.lines.exists():
        raise ValueError('The order has no lines.')
    po.status, po.approved_by = 'APPROVED', user
    po.save()


def mark_sent(po):
    if po.status != 'APPROVED':
        raise ValueError('Only approved orders can be marked as sent.')
    po.status = 'SENT'
    po.sent_date = timezone.localdate()
    if not po.expected_date:
        po.expected_date = po.sent_date + timedelta(days=po.supplier.default_lead_time_days)
    po.save()


@transaction.atomic
def receive_goods(po, quantities, user):
    """quantities: {line_id: (accepted, rejected)}. Accepted units go into stock through the ledger."""
    if po.status not in ('APPROVED', 'SENT', 'PARTIAL'):
        raise ValueError('This order cannot receive goods in its current status.')
    today = timezone.localdate()
    received_any = False
    for line in po.lines.select_related('product').select_for_update():
        accepted, rejected = quantities.get(line.pk, (0, 0))
        if accepted < 0 or rejected < 0:
            raise ValueError('Quantities cannot be negative.')
        if accepted + rejected == 0:
            continue
        if accepted + rejected > line.outstanding:
            raise ValueError(f'{line.product.name}: only {line.outstanding} unit(s) are still expected.')
        if accepted:
            post_movement(line.product, 'RECEIPT', accepted, user=user, reference=po.number,
                          note=f'Goods receipt for {po.number}')
        line.received_qty += accepted
        line.rejected_qty += rejected
        line.save()
        received_any = True
    if not received_any:
        raise ValueError('Enter a quantity for at least one line.')
    if po.first_received_date is None:
        po.first_received_date = today
    if all(line.outstanding == 0 for line in po.lines.all()):
        po.status, po.closed_date = 'CLOSED', today
    else:
        po.status = 'PARTIAL'
    po.save()


def close_short(po):
    """Close an order even though some units never arrived (lowers the supplier's fill rate)."""
    if po.status not in ('SENT', 'PARTIAL'):
        raise ValueError('Only sent or partly received orders can be closed.')
    po.status, po.closed_date = 'CLOSED', timezone.localdate()
    po.save()


def cancel(po):
    if po.status in ('PARTIAL', 'CLOSED', 'CANCELLED'):
        raise ValueError('This order can no longer be cancelled.')
    po.status = 'CANCELLED'
    po.save()
