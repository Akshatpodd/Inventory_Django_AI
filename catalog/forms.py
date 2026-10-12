import csv
import io

from django import forms

from core.forms import BootstrapForm, BootstrapModelForm

from .models import Category, Product, ProductSupplier


class CategoryForm(BootstrapModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class ProductForm(BootstrapModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'barcode', 'category', 'unit', 'cost_price', 'selling_price', 'tax_percent',
                  'reorder_point', 'min_order_qty', 'pack_size', 'shelf_life_days',
                  'preferred_supplier', 'is_active']

    def clean(self):
        data = super().clean()
        cost, price = data.get('cost_price'), data.get('selling_price')
        if cost is not None and price is not None and price < cost:
            self.add_error('selling_price', 'Selling price is below cost price.')
        return data


class ProductSupplierForm(BootstrapModelForm):
    class Meta:
        model = ProductSupplier
        fields = ['supplier', 'unit_cost', 'lead_time_days']


class ProductImportForm(BootstrapForm):
    file = forms.FileField(help_text='CSV with columns: name, sku, barcode, category, unit, cost_price, '
                                     'selling_price, tax_percent, reorder_point, min_order_qty, pack_size')

    def clean_file(self):
        upload = self.cleaned_data['file']
        if not upload.name.lower().endswith('.csv'):
            raise forms.ValidationError('Please upload a .csv file.')
        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            raise forms.ValidationError('The file must be UTF-8 text.')
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            raise forms.ValidationError('The file has no rows.')
        if 'name' not in rows[0]:
            raise forms.ValidationError('The file needs a "name" column.')
        return rows
