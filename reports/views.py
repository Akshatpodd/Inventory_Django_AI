import csv
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from catalog.models import Product
from core.forms import BootstrapForm
from core.permissions import STAFF_READ, RoleRequiredMixin
from inventory.views import filtered_movements
from purchasing.models import PurchaseOrder
from sales.models import Sale, SaleLine


# ---------------------------------------------------------------- dashboard
class DashboardView(RoleRequiredMixin, View):
    allowed_roles = STAFF_READ

    def get(self, request):
        today = timezone.localdate()
        products = list(Product.objects.filter(is_active=True).with_stock())
        stock_value = sum(max(p.stock, 0) * p.cost_price for p in products)
        low = [p for p in products if p.stock <= p.reorder_point]
        sales_qs = Sale.objects.filter(status='COMPLETED')

        def total_since(days):
            return sales_qs.filter(created_at__date__gte=today - timedelta(days=days)).aggregate(
                t=Coalesce(Sum('total'), Decimal('0')))['t']

        # sales per day for the chart (last 30 days)
        by_day = dict(sales_qs.filter(created_at__date__gte=today - timedelta(days=29))
                      .annotate(day=TruncDate('created_at')).order_by().values_list('day').annotate(t=Sum('total')))
        days = [today - timedelta(days=n) for n in range(29, -1, -1)]
        top = (SaleLine.objects.filter(sale__status='COMPLETED', sale__created_at__date__gte=today - timedelta(days=30))
               .values('product__name').annotate(units=Sum('quantity')).order_by('-units')[:5])
        return render(request, 'reports/dashboard.html', {
            'stock_value': stock_value, 'product_count': len(products), 'low_stock': low[:8], 'low_count': len(low),
            'sales_today': total_since(0), 'sales_7': total_since(6), 'sales_30': total_since(29),
            'open_pos': PurchaseOrder.objects.filter(status__in=['DRAFT', 'APPROVED', 'SENT', 'PARTIAL']).count(),
            'chart_labels': [d.strftime('%d/%m') for d in days],
            'chart_values': [float(by_day.get(d, 0)) for d in days],
            'top_products': top})


# ---------------------------------------------------------------- report framework
class DateRangeForm(BootstrapForm):
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))


class SalesSummaryForm(DateRangeForm):
    group_by = forms.ChoiceField(choices=[('day', 'Day'), ('product', 'Product'), ('category', 'Category'),
                                          ('staff', 'Staff member')], initial='day')


class BaseReport(RoleRequiredMixin, View):
    """A report returns (headers, rows). Add ?format=csv to download it."""
    allowed_roles = STAFF_READ
    title = ''
    slug = ''
    form_class = None
    description = ''

    def build(self, cleaned):
        raise NotImplementedError

    def get(self, request):
        form = self.form_class(request.GET or None) if self.form_class else None
        cleaned = form.cleaned_data if form is not None and form.is_valid() else {}
        headers, rows = self.build(cleaned)
        if request.GET.get('format') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{self.slug}.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(rows)
            return response
        query = request.GET.copy()
        query.pop('format', None)
        return render(request, 'reports/report.html', {
            'title': self.title, 'description': self.description, 'form': form, 'headers': headers,
            'rows': rows[:500], 'truncated': len(rows) > 500, 'csv_query': query.urlencode(), 'count': len(rows)})


def date_filter(qs, cleaned, field):
    if cleaned.get('date_from'):
        qs = qs.filter(**{f'{field}__date__gte': cleaned['date_from']})
    if cleaned.get('date_to'):
        qs = qs.filter(**{f'{field}__date__lte': cleaned['date_to']})
    return qs


class StockValuationReport(BaseReport):
    title, slug = 'Stock valuation', 'stock-valuation'
    description = 'Stock on hand valued at cost price.'

    def build(self, cleaned):
        rows, total = [], Decimal('0')
        for p in Product.objects.filter(is_active=True).with_stock().select_related('category').order_by('name'):
            value = max(p.stock, 0) * p.cost_price
            total += value
            rows.append([p.sku, p.name, p.category.name if p.category else '', p.stock, p.cost_price, value])
        rows.append(['', 'TOTAL', '', '', '', total])
        return ['SKU', 'Product', 'Category', 'Stock', 'Cost price', 'Value'], rows


class MovementReport(BaseReport):
    title, slug = 'Stock movement history', 'stock-movements'
    form_class = DateRangeForm

    def build(self, cleaned):
        qs = date_filter(filtered_movements(None)[1], cleaned, 'created_at')[:5000]
        return (['Date', 'Product', 'Type', 'Change', 'Reference', 'User', 'Note'],
                [[m.created_at.strftime('%d/%m/%Y %H:%M'), m.product.name, m.get_movement_type_display(), m.delta,
                  m.reference, m.user or '', m.note] for m in qs])


class SalesSummaryReport(BaseReport):
    title, slug = 'Sales summary', 'sales-summary'
    form_class = SalesSummaryForm
    description = 'Completed sales, net of returns. Choose how to group the figures.'

    def build(self, cleaned):
        group = cleaned.get('group_by', 'day')
        lines = date_filter(SaleLine.objects.filter(sale__status='COMPLETED'), cleaned, 'sale__created_at')
        revenue = ExpressionWrapper((F('quantity') - F('returned_qty')) * F('unit_price'),
                                    output_field=DecimalField(max_digits=14, decimal_places=2))
        cost = ExpressionWrapper((F('quantity') - F('returned_qty')) * F('unit_cost'),
                                 output_field=DecimalField(max_digits=14, decimal_places=2))
        key = {'day': TruncDate('sale__created_at'), 'product': F('product__name'),
               'category': Coalesce(F('product__category__name'), Value('Uncategorised')),
               'staff': Coalesce(F('sale__created_by__username'), Value('Unknown'))}[group]
        data = (lines.annotate(grp=key).values('grp')
                .annotate(units=Sum(F('quantity') - F('returned_qty')), revenue=Sum(revenue), cost=Sum(cost),
                          bills=Count('sale', distinct=True)).order_by('grp' if group != 'product' else '-revenue'))
        rows = [[(r['grp'].strftime('%d/%m/%Y') if group == 'day' else r['grp']), r['bills'], r['units'],
                 r['revenue'], r['revenue'] - r['cost']] for r in data]
        return [group.title(), 'Bills', 'Units', 'Revenue (ex tax)', 'Gross margin'], rows


class PurchaseReport(BaseReport):
    title, slug = 'Purchases by supplier', 'purchases'
    form_class = DateRangeForm

    def build(self, cleaned):
        qs = date_filter(PurchaseOrder.objects.exclude(status='CANCELLED').select_related('supplier'),
                         cleaned, 'created_at')
        rows = [[o.number, o.supplier.name, o.get_status_display(), o.order_date.strftime('%d/%m/%Y'),
                 o.lead_time_days if o.lead_time_days is not None else '', o.total] for o in qs]
        return ['Order', 'Supplier', 'Status', 'Order date', 'Lead time (days)', 'Value'], rows


REPORTS = [StockValuationReport, MovementReport, SalesSummaryReport, PurchaseReport]


class ReportIndexView(RoleRequiredMixin, View):
    allowed_roles = STAFF_READ

    def get(self, request):
        return render(request, 'reports/index.html', {'reports': [
            {'title': r.title, 'slug': r.slug, 'description': r.description} for r in REPORTS]})
