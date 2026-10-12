from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView

from core.permissions import MANAGERS, SELLERS, STAFF_READ, RoleRequiredMixin, user_has_role
from inventory.services import InsufficientStock

from . import services
from .forms import SaleFilterForm, SaleHeaderForm, SaleLineFormSet
from .models import Sale


class SaleListView(RoleRequiredMixin, View):
    allowed_roles = STAFF_READ

    def get(self, request):
        form = SaleFilterForm(request.GET or None)
        qs = Sale.objects.select_related('created_by')
        if form.is_valid():
            d = form.cleaned_data
            if d['q']:
                qs = qs.filter(Q(number__icontains=d['q']) | Q(customer_name__icontains=d['q']))
            if d['date_from']:
                qs = qs.filter(created_at__date__gte=d['date_from'])
            if d['date_to']:
                qs = qs.filter(created_at__date__lte=d['date_to'])
        query = request.GET.copy()
        query.pop('page', None)
        return render(request, 'sales/list.html', {
            'form': form, 'page': Paginator(qs, 25).get_page(request.GET.get('page')),
            'can_sell': user_has_role(request.user, SELLERS), 'querystring': query.urlencode()})


class SaleCreateView(RoleRequiredMixin, View):
    allowed_roles = SELLERS
    template_name = 'sales/form.html'

    def get(self, request):
        return render(request, self.template_name, {'header': SaleHeaderForm(), 'formset': SaleLineFormSet()})

    def post(self, request):
        header = SaleHeaderForm(request.POST)
        formset = SaleLineFormSet(request.POST)
        context = {'header': header, 'formset': formset}
        if not (header.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        # combine rows that name the same product, so stock is checked against the total
        combined = {}
        for form in formset:
            d = form.cleaned_data
            if not d.get('product'):
                continue
            product = d['product']
            price = d.get('unit_price')
            price = product.selling_price if price in (None, '') else price
            if product.pk in combined:
                combined[product.pk][1] += d['quantity']
            else:
                combined[product.pk] = [product, d['quantity'], price]
        items = [tuple(v) for v in combined.values()]
        if not items:
            messages.error(request, 'Add at least one product.')
            return render(request, self.template_name, context)
        try:
            sale = services.create_sale(header.cleaned_data['customer_name'], header.cleaned_data['customer_phone'],
                                        header.cleaned_data['discount'] or 0, items, request.user,
                                        note=header.cleaned_data['note'])
        except (InsufficientStock, ValueError) as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, context)
        messages.success(request, f'Sale {sale.number} saved. Total Rs {sale.total}.')
        return redirect('sales:detail', pk=sale.pk)


class SaleDetailView(RoleRequiredMixin, DetailView):
    model = Sale
    template_name = 'sales/detail.html'
    allowed_roles = STAFF_READ

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['lines'] = self.object.lines.select_related('product')
        ctx['can_manage'] = user_has_role(self.request.user, MANAGERS)
        return ctx


class InvoiceView(SaleDetailView):
    template_name = 'sales/invoice.html'


class SaleCancelView(RoleRequiredMixin, View):
    allowed_roles = MANAGERS

    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        try:
            services.cancel_sale(sale, request.user)
            messages.success(request, f'{sale.number} cancelled and stock restored.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('sales:detail', pk=pk)


class SaleReturnView(RoleRequiredMixin, View):
    allowed_roles = MANAGERS
    template_name = 'sales/return.html'

    def get(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        return render(request, self.template_name, {'sale': sale, 'lines': sale.lines.select_related('product')})

    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        try:
            quantities = {line.pk: int(request.POST.get(f'return_{line.pk}') or 0) for line in sale.lines.all()}
            refund = services.return_items(sale, quantities, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('sales:return', pk=pk)
        messages.success(request, f'Return saved. Refund due: Rs {refund}.')
        return redirect('sales:detail', pk=pk)
