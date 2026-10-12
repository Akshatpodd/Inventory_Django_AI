from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from core.permissions import MANAGERS, STAFF_READ, RoleRequiredMixin, user_has_role

from . import services
from .forms import LineFormSet, PurchaseOrderForm
from .models import PurchaseOrder


class POListView(RoleRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchasing/list.html'
    allowed_roles = STAFF_READ
    paginate_by = 25

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related('supplier')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        status = self.request.GET.get('status', '')
        ctx.update(statuses=PurchaseOrder.STATUS_CHOICES, current_status=status,
                   querystring=f'status={status}' if status else '',
                   can_write=user_has_role(self.request.user, MANAGERS))
        return ctx


class POEditView(RoleRequiredMixin, View):
    """Create a new order or edit a draft (header + lines in one page)."""
    allowed_roles = MANAGERS
    template_name = 'purchasing/form.html'

    def get_order(self, pk):
        return get_object_or_404(PurchaseOrder, pk=pk) if pk else None

    def get(self, request, pk=None):
        order = self.get_order(pk)
        if order and not order.is_editable:
            messages.error(request, 'Only draft orders can be edited.')
            return redirect('purchasing:detail', pk=order.pk)
        return render(request, self.template_name, {
            'form': PurchaseOrderForm(instance=order), 'formset': LineFormSet(instance=order), 'order': order})

    @transaction.atomic
    def post(self, request, pk=None):
        order = self.get_order(pk)
        if order and not order.is_editable:
            messages.error(request, 'Only draft orders can be edited.')
            return redirect('purchasing:detail', pk=order.pk)
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = LineFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            if order.pk is None:
                order.created_by = request.user
            order.save()
            formset.instance = order
            formset.save()
            messages.success(request, f'Purchase order {order.number} saved.')
            return redirect('purchasing:detail', pk=order.pk)
        return render(request, self.template_name, {'form': form, 'formset': formset, 'order': order})


class PODetailView(RoleRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchasing/detail.html'
    allowed_roles = STAFF_READ

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['lines'] = self.object.lines.select_related('product')
        ctx['can_write'] = user_has_role(self.request.user, MANAGERS)
        return ctx


class POPrintView(PODetailView):
    template_name = 'purchasing/print.html'


class POActionView(RoleRequiredMixin, View):
    """POST actions: approve, send, close, cancel."""
    allowed_roles = MANAGERS

    def post(self, request, pk, action):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            if action == 'approve':
                services.approve(order, request.user)
            elif action == 'send':
                services.mark_sent(order)
            elif action == 'close':
                services.close_short(order)
            elif action == 'cancel':
                services.cancel(order)
            else:
                raise ValueError('Unknown action.')
            messages.success(request, f'{order.number}: {action} done.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('purchasing:detail', pk=order.pk)


class POReceiveView(RoleRequiredMixin, View):
    allowed_roles = MANAGERS
    template_name = 'purchasing/receive.html'

    def get(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        return render(request, self.template_name, {'order': order, 'lines': order.lines.select_related('product')})

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        quantities = {}
        try:
            for line in order.lines.all():
                accepted = int(request.POST.get(f'accepted_{line.pk}') or 0)
                rejected = int(request.POST.get(f'rejected_{line.pk}') or 0)
                quantities[line.pk] = (accepted, rejected)
            services.receive_goods(order, quantities, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('purchasing:receive', pk=order.pk)
        messages.success(request, 'Goods received and stock updated.')
        return redirect('purchasing:detail', pk=order.pk)
