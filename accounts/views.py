from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView

from core.permissions import ADMINS, RoleRequiredMixin
from core.views import CrudCreateView, CrudListView, CrudUpdateView, DeactivateView

from .forms import AdminSetPasswordForm, LockoutAuthenticationForm, UserCreateForm, UserEditForm

User = get_user_model()


class IMSLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = LockoutAuthenticationForm
    redirect_authenticated_user = True


class UserListView(CrudListView):
    model = User
    allowed_roles = ADMINS
    write_roles = ADMINS
    title = 'Users'
    ordering = ['username']
    columns = [('Username', 'username'), ('Name', 'display_name'), ('Email', 'email'),
               ('Role', 'get_role_display'), ('Active', lambda u: 'Yes' if u.is_active else 'No')]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    create_url = 'accounts:user_create'
    edit_url = 'accounts:user_edit'
    delete_url = 'accounts:user_toggle'
    delete_label = 'Activate / Deactivate'
    row_links = [('Reset password', 'accounts:user_password')]


class UserCreateView(CrudCreateView):
    model = User
    form_class = UserCreateForm
    allowed_roles = ADMINS
    title = 'Add user'
    success_url_name = 'accounts:user_list'
    success_message = 'User created.'


class UserUpdateView(CrudUpdateView):
    model = User
    form_class = UserEditForm
    allowed_roles = ADMINS
    title = 'Edit user'
    success_url_name = 'accounts:user_list'


class UserToggleView(DeactivateView):
    model = User
    allowed_roles = ADMINS
    success_url_name = 'accounts:user_list'

    def post(self, request, *args, **kwargs):
        if self.get_object() == request.user:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect(self.success_url_name)
        return super().post(request, *args, **kwargs)


class UserPasswordView(RoleRequiredMixin, FormView):
    template_name = 'crud/form.html'
    allowed_roles = ADMINS
    form_class = AdminSetPasswordForm

    def dispatch(self, request, *args, **kwargs):
        self.target = get_object_or_404(User, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.target
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, f'Password changed for {self.target}.')
        return redirect('accounts:user_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f'Reset password: {self.target}', cancel_url=reverse('accounts:user_list'))
        return ctx
