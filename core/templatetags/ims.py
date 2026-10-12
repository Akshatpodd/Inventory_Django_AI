from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    return mapping.get(key)


@register.filter
def badge_class(value):
    """Bootstrap colour for common status words."""
    value = str(value).upper()
    good = {'APPROVED', 'COMPLETED', 'CLOSED', 'OK', 'ACTIVE', 'YES'}
    warn = {'DRAFT', 'PARTIAL', 'SENT'}
    bad = {'CANCELLED', 'LOW', 'NO', 'INACTIVE'}
    if value in good:
        return 'success'
    if value in warn:
        return 'warning text-dark'
    if value in bad:
        return 'danger'
    return 'secondary'


@register.filter
def path_active(path, url):
    """True when the current page belongs to the menu item that points to `url`."""
    return path == url if url == '/' else path.startswith(url)
