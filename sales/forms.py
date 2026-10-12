from django import forms
from django.forms import formset_factory

from catalog.models import Product
from core.forms import BootstrapForm


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.sku} - {obj.name} (stock {getattr(obj, "stock", "?")}, Rs {obj.selling_price})'


class SaleHeaderForm(BootstrapForm):
    customer_name = forms.CharField(max_length=150, required=False, initial='Walk-in customer')
    customer_phone = forms.RegexField(r'^[6-9]\d{9}$', required=False, max_length=10,
                                      error_messages={'invalid': 'Enter a 10 digit mobile number.'})
    discount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, required=False, initial=0)
    note = forms.CharField(max_length=255, required=False)


class SaleLineForm(BootstrapForm):
    product = ProductChoiceField(queryset=Product.objects.none(), required=False)
    quantity = forms.IntegerField(min_value=1, required=False)
    unit_price = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, required=False,
                                    help_text='Leave empty to use the product price')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True).with_stock()

    def clean(self):
        data = super().clean()
        if data.get('product') and not data.get('quantity'):
            self.add_error('quantity', 'Enter a quantity.')
        return data


SaleLineFormSet = formset_factory(SaleLineForm, extra=6)


class SaleFilterForm(BootstrapForm):
    q = forms.CharField(required=False, label='Search', widget=forms.TextInput(attrs={'placeholder': 'Invoice or customer'}))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
