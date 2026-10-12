from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import FormView

from catalog.models import Product
from core.permissions import MANAGERS, STAFF_READ, RoleRequiredMixin

from .forms import AdjustmentForm, MovementFilterForm
from .models import StockMovement
from .services import InsufficientStock, post_movement


def filtered_movements(params):
    """Used by the ledger page and by the CSV report."""
    form = MovementFilterForm(params or None)
    qs = StockMovement.objects.select_related('product', 'user')
    if form.is_valid():
        d = form.cleaned_data
        if d['product']:
            qs = qs.filter(product=d['product'])
        if d['movement_type']:
            qs = qs.filter(movement_type=d['movement_type'])
        if d['date_from']:
            qs = qs.filter(created_at__date__gte=d['date_from'])
        if d['date_to']:
            qs = qs.filter(created_at__date__lte=d['date_to'])
        if d['needs_review']:
            qs = qs.filter(needs_review=True)
    return form, qs


class MovementListView(RoleRequiredMixin, View):
    allowed_roles = STAFF_READ

    def get(self, request):
        form, qs = filtered_movements(request.GET)
        page = Paginator(qs, 30).get_page(request.GET.get('page'))
        query = request.GET.copy()
        query.pop('page', None)
        can_write = request.user.is_superuser or request.user.role in MANAGERS
        return render(request, 'inventory/movements.html', {
            'form': form, 'page': page, 'can_write': can_write, 'querystring': query.urlencode()})

    def post(self, request):
        """Mark a flagged adjustment as reviewed."""
        if not (request.user.is_superuser or request.user.role in MANAGERS):
            messages.error(request, 'Only managers can review adjustments.')
            return redirect('inventory:movements')
        StockMovement.objects.filter(pk=request.POST.get('movement_id')).update(
            needs_review=False, reviewed_by=request.user)
        messages.success(request, 'Marked as reviewed.')
        return redirect(request.META.get('HTTP_REFERER') or 'inventory:movements')


class AdjustmentView(RoleRequiredMixin, FormView):
    template_name = 'crud/form.html'
    form_class = AdjustmentForm
    allowed_roles = MANAGERS

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title='Stock adjustment', cancel_url='/inventory/',
                   note='Every adjustment needs a reason. Large adjustments are flagged for review.')
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            movement = post_movement(d['product'], d['movement_type'], d['quantity'], user=self.request.user,
                                     reason_code=d['reason_code'], note=d['note'], reference='Manual adjustment')
        except InsufficientStock as exc:
            form.add_error('quantity', str(exc))
            return self.form_invalid(form)
        if movement.needs_review:
            messages.warning(self.request, 'Adjustment saved and flagged for review because it is large.')
        else:
            messages.success(self.request, 'Adjustment saved.')
        return redirect('inventory:movements')


class StockTakeView(RoleRequiredMixin, View):
    """Physical count: type the counted quantity; differences are posted as adjustments."""
    allowed_roles = MANAGERS

    def get(self, request):
        products = Product.objects.filter(is_active=True).with_stock().select_related('category').order_by('name')
        return render(request, 'inventory/stocktake.html', {'products': products})

    def post(self, request):
        posted = 0
        for product in Product.objects.filter(is_active=True).with_stock():
            raw = request.POST.get(f'count_{product.pk}', '').strip()
            if raw == '':
                continue
            if not raw.isdigit():
                messages.error(request, f'{product.name}: "{raw}" is not a valid count; skipped.')
                continue
            difference = int(raw) - product.stock
            if difference == 0:
                continue
            post_movement(product, 'ADJUST_IN' if difference > 0 else 'ADJUST_OUT', abs(difference),
                          user=request.user, reason_code='COUNT',
                          note=f'Stock-take {timezone.localdate():%d/%m/%Y}: system {product.stock}, counted {raw}',
                          reference='Stock-take', allow_negative=True)
            posted += 1
        messages.success(request, f'Stock-take saved: {posted} difference(s) posted as adjustments.')
        return redirect('inventory:movements')
