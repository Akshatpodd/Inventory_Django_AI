"""Role names and helpers. This file must NOT import anything from django.contrib.auth:
accounts/models.py imports it while Django is still loading the models."""

ADMIN, MANAGER, SALES, VIEWER = 'ADMIN', 'MANAGER', 'SALES', 'VIEWER'

ROLE_CHOICES = [
    (ADMIN, 'Admin'),
    (MANAGER, 'Inventory Manager'),
    (SALES, 'Sales / Billing Staff'),
    (VIEWER, 'Viewer / Auditor'),
]

# Handy groups of roles
EVERYONE = (ADMIN, MANAGER, SALES, VIEWER)
STAFF_READ = (ADMIN, MANAGER, SALES, VIEWER)
MANAGERS = (ADMIN, MANAGER)
SELLERS = (ADMIN, MANAGER, SALES)
ADMINS = (ADMIN,)


def user_has_role(user, roles):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'role', None) in roles)
