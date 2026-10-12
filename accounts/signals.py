from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.utils import timezone


@receiver(user_login_failed)
def count_failed_login(sender, credentials, **kwargs):
    """After too many wrong passwords the account is locked for a while."""
    User = get_user_model()
    username = credentials.get(User.USERNAME_FIELD)
    user = User.objects.filter(**{User.USERNAME_FIELD: username}).first() if username else None
    if not user:
        return
    user.failed_attempts += 1
    if user.failed_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
        user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        user.failed_attempts = 0
    user.save(update_fields=['failed_attempts', 'locked_until'])


@receiver(user_logged_in)
def reset_failed_attempts(sender, user, **kwargs):
    if user.failed_attempts or user.locked_until:
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=['failed_attempts', 'locked_until'])
