from django import forms

from catalog.models import Product
from core.forms import BootstrapForm

from .models import StockMovement


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.sku} - {obj.name} (stock {getattr(obj, "stock", "?")})'


class AdjustmentForm(BootstrapForm):
    DIRECTIONS = [('ADJUST_IN', 'Add stock'), ('ADJUST_OUT', 'Remove stock'), ('DAMAGE', 'Damaged / expired')]
    product = ProductChoiceField(queryset=Product.objects.none())
    movement_type = forms.ChoiceField(choices=DIRECTIONS, label='Type')
    quantity = forms.IntegerField(min_value=1)
    reason_code = forms.ChoiceField(choices=StockMovement.REASON_CHOICES, label='Reason')
    note = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True).with_stock()


class MovementFilterForm(BootstrapForm):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), required=False)
    movement_type = forms.ChoiceField(choices=[('', 'All types')] + StockMovement.TYPE_CHOICES, required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    needs_review = forms.BooleanField(required=False, label='Only items needing review')
