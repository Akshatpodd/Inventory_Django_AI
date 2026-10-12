from core.views import CrudCreateView, CrudListView, CrudUpdateView, DeactivateView

from .forms import SupplierForm
from .models import Supplier


class SupplierListView(CrudListView):
    model = Supplier
    ordering = ['name']
    title = 'Suppliers'
    columns = [('Name', 'name'), ('Contact', 'contact_person'), ('Phone', 'phone'), ('Email', 'email'),
               ('Lead time (days)', 'default_lead_time_days'), ('Active', lambda s: 'Yes' if s.is_active else 'No')]
    search_fields = ['name', 'contact_person', 'phone', 'email']
    create_url = 'suppliers:create'
    edit_url = 'suppliers:edit'
    delete_url = 'suppliers:toggle'
    delete_label = 'Activate / Deactivate'


class SupplierCreateView(CrudCreateView):
    model = Supplier
    form_class = SupplierForm
    title = 'Add supplier'
    success_url_name = 'suppliers:list'


class SupplierUpdateView(CrudUpdateView):
    model = Supplier
    form_class = SupplierForm
    title = 'Edit supplier'
    success_url_name = 'suppliers:list'


class SupplierToggleView(DeactivateView):
    model = Supplier
    success_url_name = 'suppliers:list'
