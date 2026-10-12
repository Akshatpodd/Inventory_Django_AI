from contextvars import ContextVar

_current_user = ContextVar('audit_user', default=None)


def get_current_user():
    user = _current_user.get()
    return user if user is not None and getattr(user, 'is_authenticated', False) else None


class CurrentUserMiddleware:
    """Remembers who is making the request, so the audit log can name them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_user.set(getattr(request, 'user', None))
        try:
            return self.get_response(request)
        finally:
            _current_user.reset(token)
