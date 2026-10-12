"""Small generic list / create / edit / delete views so every screen looks and works the same."""
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView, View
from django.views.generic.detail import SingleObjectMixin

from .permissions import MANAGERS, STAFF_READ, RoleRequiredMixin


def resolve(obj, accessor):
    """Read a value from an object. accessor is 'field', 'relation__field' or a callable."""
    if callable(accessor):
        return accessor(obj)
    value = obj
    for part in accessor.split('__'):
        value = getattr(value, part, None)
        if value is None:
            return ''
        if callable(value):
            value = value()
    return value


class CrudListView(RoleRequiredMixin, ListView):
    """List with search, paging and edit / deactivate links.

    columns: list of (header, accessor). Optional: search_fields, create_url, edit_url, delete_url, detail_url.
    """
    template_name = 'crud/list.html'
    allowed_roles = STAFF_READ
    write_roles = MANAGERS
    paginate_by = 25
    columns = []
    search_fields = []
    title = ''
    create_url = edit_url = delete_url = detail_url = None
    delete_label = 'Deactivate'
    extra_links = []        # buttons above the table: (label, url_name) without arguments
    row_links = []          # links in every row: (label, url_name) called with the row's id

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q and self.search_fields:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f'{field}__icontains': q})
            qs = qs.filter(cond)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        can_write = getattr(self.request.user, 'is_superuser', False) or getattr(
            self.request.user, 'role', None) in self.write_roles
        rows = [{'obj': o, 'cells': [(h, resolve(o, acc)) for h, acc in self.columns]} for o in ctx['object_list']]
        ctx.update(title=self.title, headers=[h for h, _ in self.columns], rows=rows,
                   can_write=can_write, q=self.request.GET.get('q', ''), searchable=bool(self.search_fields),
                   querystring=urlencode({'q': self.request.GET['q']}) if self.request.GET.get('q') else '',
                   create_url=self.create_url, edit_url=self.edit_url, delete_url=self.delete_url,
                   detail_url=self.detail_url, delete_label=self.delete_label, extra_links=self.extra_links,
                   row_links=self.row_links)
        return ctx


class CrudFormMixin:
    template_name = 'crud/form.html'
    allowed_roles = MANAGERS
    title = ''
    success_url_name = None
    success_message = 'Saved.'

    def get_success_url(self):
        return reverse(self.success_url_name)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = self.title
        ctx['cancel_url'] = self.get_success_url()
        return ctx


class CrudCreateView(CrudFormMixin, RoleRequiredMixin, CreateView):
    success_message = 'Created.'


class CrudUpdateView(CrudFormMixin, RoleRequiredMixin, UpdateView):
    pass


class DeactivateView(RoleRequiredMixin, SingleObjectMixin, View):
    """POST-only: set is_active to False instead of deleting (keeps history)."""
    allowed_roles = MANAGERS
    success_url_name = None
    flag = 'is_active'

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        setattr(obj, self.flag, not getattr(obj, self.flag))
        obj.save()
        state = 'activated' if getattr(obj, self.flag) else 'deactivated'
        messages.success(request, f'{obj} {state}.')
        return redirect(self.success_url_name)
