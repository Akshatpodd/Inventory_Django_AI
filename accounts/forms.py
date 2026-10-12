from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.forms import BootstrapFormMixin

User = get_user_model()


class LockoutAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """Login form that refuses a locked account even when the password is right."""

    def clean(self):
        username = self.cleaned_data.get('username')
        user = User.objects.filter(username=username).first() if username else None
        if user and user.locked_until and user.locked_until > timezone.now():
            minutes = int((user.locked_until - timezone.now()).total_seconds() // 60) + 1
            raise ValidationError(f'Too many failed attempts. Try again in about {minutes} minute(s).',
                                  code='locked')
        return super().clean()


class UserCreateForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'role')


class UserEditForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'role', 'is_active')


class AdminSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass
