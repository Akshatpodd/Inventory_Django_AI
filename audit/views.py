from django.views.generic import ListView

from core.permissions import ADMINS, RoleRequiredMixin

from .models import AuditLog


class AuditListView(RoleRequiredMixin, ListView):
    allowed_roles = ADMINS + ('VIEWER',)
    model = AuditLog
    template_name = 'audit/list.html'
    paginate_by = 40

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user')
        model, user = self.request.GET.get('model'), self.request.GET.get('user')
        if model:
            qs = qs.filter(model=model)
        if user:
            qs = qs.filter(user__username__icontains=user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['models'] = AuditLog.objects.order_by().values_list('model', flat=True).distinct()
        ctx['current_model'] = self.request.GET.get('model', '')
        ctx['current_user'] = self.request.GET.get('user', '')
        return ctx
