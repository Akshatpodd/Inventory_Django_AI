"""The permission mixin used by every view. Role constants live in core/roles.py."""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .roles import (ADMIN, ADMINS, EVERYONE, MANAGER, MANAGERS, ROLE_CHOICES, SALES, SELLERS,  # noqa: F401
                    STAFF_READ, VIEWER, user_has_role)


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Set `allowed_roles` on a view. Anyone else gets a 403 page."""
    allowed_roles = EVERYONE

    def test_func(self):
        return user_has_role(self.request.user, self.allowed_roles)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied