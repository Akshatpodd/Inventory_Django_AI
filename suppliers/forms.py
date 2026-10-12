from core.forms import BootstrapModelForm

from .models import Supplier


class SupplierForm(BootstrapModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'payment_terms',
                  'default_lead_time_days', 'is_active']
