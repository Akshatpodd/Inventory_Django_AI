"""Builds the sidebar menu for the logged-in user's role."""
from .permissions import ADMINS, STAFF_READ, user_has_role

MENU = [
    # (label, url name, roles allowed to see it)
    ('Dashboard', 'reports:dashboard', STAFF_READ),
    ('Products', 'catalog:product_list', STAFF_READ),
    ('Categories', 'catalog:category_list', STAFF_READ),
    ('Suppliers', 'suppliers:list', STAFF_READ),
    ('Stock Ledger', 'inventory:movements', STAFF_READ),
    ('Purchase Orders', 'purchasing:list', STAFF_READ),
    ('Sales', 'sales:list', STAFF_READ),
    ('Reports', 'reports:index', STAFF_READ),
    ('Users', 'accounts:user_list', ADMINS),
    ('Audit Log', 'audit:list', ADMINS + ('VIEWER',)),
]


def navigation(request):
    if not request.user.is_authenticated:
        return {}
    items = [{'label': label, 'url': url} for label, url, roles in MENU if user_has_role(request.user, roles)]
    return {'menu_items': items}
