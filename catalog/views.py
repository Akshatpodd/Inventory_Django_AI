import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, FormView, View

from core.permissions import MANAGERS, STAFF_READ, RoleRequiredMixin
from core.views import CrudCreateView, CrudListView, CrudUpdateView, DeactivateView

from .forms import CategoryForm, ProductForm, ProductImportForm, ProductSupplierForm
from .models import Category, Product, ProductSupplier


# ---------------------------------------------------------------- categories
class CategoryListView(CrudListView):
    model = Category
    ordering = ['name']
    title = 'Categories'
    columns = [('Name', 'name'), ('Description', 'description'), ('Products', lambda c: c.products.count())]
    search_fields = ['name']
    create_url = 'catalog:category_create'
    edit_url = 'catalog:category_edit'


class CategoryCreateView(CrudCreateView):
    model = Category
    form_class = CategoryForm
    title = 'Add category'
    success_url_name = 'catalog:category_list'


class CategoryUpdateView(CrudUpdateView):
    model = Category
    form_class = CategoryForm
    title = 'Edit category'
    success_url_name = 'catalog:category_list'


# ---------------------------------------------------------------- products
class ProductListView(CrudListView):
    title = 'Products'
    columns = [('SKU', 'sku'), ('Name', 'name'), ('Category', 'category__name'), ('Unit', 'unit'),
               ('Cost', 'cost_price'), ('Price', 'selling_price'), ('Stock', 'stock'),
               ('Reorder at', 'reorder_point'),
               ('Status', lambda p: 'LOW' if p.stock <= p.reorder_point else 'OK')]
    search_fields = ['name', 'sku', 'barcode', 'category__name']
    create_url = 'catalog:product_create'
    edit_url = 'catalog:product_edit'
    detail_url = 'catalog:product_detail'
    delete_url = 'catalog:product_toggle'
    delete_label = 'Activate / Deactivate'
    extra_links = [('Import CSV', 'catalog:product_import'), ('Export CSV', 'catalog:product_export')]

    def get_queryset(self):
        self.queryset = Product.objects.with_stock().select_related('category')
        return super().get_queryset()


class ProductCreateView(CrudCreateView):
    model = Product
    form_class = ProductForm
    title = 'Add product'
    success_url_name = 'catalog:product_list'


class ProductUpdateView(CrudUpdateView):
    model = Product
    form_class = ProductForm
    title = 'Edit product'
    success_url_name = 'catalog:product_list'


class ProductToggleView(DeactivateView):
    model = Product
    success_url_name = 'catalog:product_list'


class ProductDetailView(RoleRequiredMixin, DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    allowed_roles = STAFF_READ

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object
        ctx['stock'] = product.stock_on_hand
        ctx['supplier_links'] = product.supplier_links.select_related('supplier')
        ctx['movements'] = product.movements.select_related('user')[:15]
        ctx['can_write'] = self.request.user.is_superuser or self.request.user.role in MANAGERS
        return ctx


class ProductSupplierAddView(CrudCreateView):
    model = ProductSupplier
    form_class = ProductSupplierForm
    title = 'Add supplier for product'

    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, pk=kwargs['product_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.product = self.product
        existing = ProductSupplier.objects.filter(product=self.product, supplier=form.cleaned_data['supplier']).first()
        if existing:   # update instead of failing on the unique constraint
            existing.unit_cost = form.cleaned_data['unit_cost']
            existing.lead_time_days = form.cleaned_data['lead_time_days']
            existing.save()
            messages.success(self.request, 'Supplier link updated.')
            return redirect(self.get_success_url())
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('catalog:product_detail', args=[self.product.pk])


class ProductSupplierRemoveView(RoleRequiredMixin, View):
    allowed_roles = MANAGERS

    def post(self, request, pk):
        link = get_object_or_404(ProductSupplier, pk=pk)
        product_pk = link.product_id
        link.delete()
        messages.success(request, 'Supplier link removed.')
        return redirect('catalog:product_detail', pk=product_pk)


# ---------------------------------------------------------------- CSV import / export
class ProductExportView(RoleRequiredMixin, View):
    allowed_roles = STAFF_READ

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products.csv"'
        writer = csv.writer(response)
        writer.writerow(['sku', 'barcode', 'name', 'category', 'unit', 'cost_price', 'selling_price', 'tax_percent',
                         'reorder_point', 'min_order_qty', 'pack_size', 'stock', 'active'])
        for p in Product.objects.with_stock().select_related('category'):
            writer.writerow([p.sku, p.barcode or '', p.name, p.category.name if p.category else '', p.unit,
                             p.cost_price, p.selling_price, p.tax_percent, p.reorder_point, p.min_order_qty,
                             p.pack_size, p.stock, 'yes' if p.is_active else 'no'])
        return response


class ProductImportView(RoleRequiredMixin, FormView):
    template_name = 'crud/form.html'
    form_class = ProductImportForm
    allowed_roles = MANAGERS

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title='Import products from CSV', cancel_url=reverse('catalog:product_list'),
                   multipart=True, note='Existing products (same SKU) are updated; new ones are created. '
                                        'Stock is not changed by an import: use Stock Ledger > Adjust.')
        return ctx

    @staticmethod
    def _decimal(value, default='0'):
        try:
            return Decimal(str(value).strip() or default)
        except InvalidOperation:
            raise ValueError(f'"{value}" is not a number')

    def form_valid(self, form):
        created = updated = 0
        errors = []
        for line_no, row in enumerate(form.cleaned_data['file'], start=2):
            name = (row.get('name') or '').strip()
            if not name:
                errors.append(f'Row {line_no}: name is empty')
                continue
            try:
                category = None
                if (row.get('category') or '').strip():
                    category, _ = Category.objects.get_or_create(name=row['category'].strip())
                values = dict(
                    name=name, category=category, unit=(row.get('unit') or 'PCS').strip().upper() or 'PCS',
                    cost_price=self._decimal(row.get('cost_price')), selling_price=self._decimal(row.get('selling_price')),
                    tax_percent=self._decimal(row.get('tax_percent')),
                    reorder_point=int(self._decimal(row.get('reorder_point'))),
                    min_order_qty=max(int(self._decimal(row.get('min_order_qty'), '1')), 1),
                    pack_size=max(int(self._decimal(row.get('pack_size'), '1')), 1),
                    barcode=(row.get('barcode') or '').strip() or None)
                if values['unit'] not in dict(Product.UNIT_CHOICES):
                    raise ValueError(f'unit "{values["unit"]}" is not valid')
                sku = (row.get('sku') or '').strip()
                product = Product.objects.filter(sku=sku).first() if sku else None
                if product:
                    for key, val in values.items():
                        setattr(product, key, val)
                    product.save()
                    updated += 1
                else:
                    Product.objects.create(sku=sku, **values)
                    created += 1
            except Exception as exc:    # one bad row must not stop the import
                errors.append(f'Row {line_no}: {exc}')
        messages.success(self.request, f'Import finished: {created} created, {updated} updated.')
        if errors:
            messages.warning(self.request, 'Skipped rows: ' + '; '.join(errors[:8]) +
                             (f' ... and {len(errors) - 8} more' if len(errors) > 8 else ''))
        return redirect('catalog:product_list')
