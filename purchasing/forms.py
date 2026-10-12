from django import forms
from django.forms import inlineformset_factory

from catalog.models import Product
from core.forms import BootstrapModelForm

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderForm(BootstrapModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'order_date', 'expected_date', 'note']
        widgets = {'order_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'expected_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from suppliers.models import Supplier
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)


class PurchaseOrderLineForm(BootstrapModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ['product', 'quantity', 'unit_cost']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)


LineFormSet = inlineformset_factory(PurchaseOrder, PurchaseOrderLine, form=PurchaseOrderLineForm,
                                    extra=3, can_delete=True, min_num=0)
