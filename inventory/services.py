"""All stock changes go through here, inside a database transaction ."""
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import Product

from .models import DIRECTION, StockMovement


class InsufficientStock(Exception):
    def __init__(self, product, available, requested):
        self.product, self.available, self.requested = product, available, requested
        super().__init__(f'Not enough stock for {product.name}: {available} available, {requested} requested.')


def current_stock(product):
    return product.movements.aggregate(total=Coalesce(Sum('delta'), 0))['total']


@transaction.atomic
def post_movement(product, movement_type, quantity, user=None, reason_code='', note='', reference='',
                  when=None, allow_negative=False):
    """Record one stock movement. `quantity` is always positive; the type decides the direction."""
    if movement_type not in DIRECTION:
        raise ValueError(f'Unknown movement type {movement_type}')
    quantity = int(quantity)
    if quantity <= 0:
        raise ValueError('Quantity must be greater than zero.')
    sign = DIRECTION[movement_type]
    # Lock the product row so two people cannot sell the last unit at the same moment
    product = Product.objects.select_for_update().get(pk=product.pk)
    if sign < 0 and not allow_negative:
        available = current_stock(product)
        if available < quantity:
            raise InsufficientStock(product, available, quantity)
    needs_review = movement_type in ('ADJUST_IN', 'ADJUST_OUT', 'DAMAGE') and quantity >= settings.ADJUSTMENT_REVIEW_QTY
    return StockMovement.objects.create(
        product=product, movement_type=movement_type, delta=sign * quantity, reason_code=reason_code,
        note=note, reference=reference, user=user, created_at=when or timezone.now(), needs_review=needs_review)
