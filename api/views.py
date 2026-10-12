"""Read-only REST API. Authenticate with a token from POST /api/token/."""
from rest_framework import permissions, viewsets

from catalog.models import Product
from core.permissions import STAFF_READ, user_has_role
from purchasing.models import PurchaseOrder
from sales.models import Sale

from .serializers import ProductSerializer, PurchaseOrderSerializer, SaleSerializer


class RoleReadPermission(permissions.BasePermission):
    """Only safe (read) methods, and only for users whose role may see the data."""
    roles = STAFF_READ

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS and user_has_role(request.user, getattr(view, 'roles', self.roles))


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [RoleReadPermission]
    queryset = Product.objects.with_stock().select_related('category')


class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [RoleReadPermission]
    queryset = Sale.objects.prefetch_related('lines__product')


class PurchaseOrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [RoleReadPermission]
    queryset = PurchaseOrder.objects.select_related('supplier').prefetch_related('lines__product')

