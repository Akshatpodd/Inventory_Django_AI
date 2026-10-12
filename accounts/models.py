from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.roles import ADMIN, ROLE_CHOICES, VIEWER


class User(AbstractUser):
    """Staff account with a role. Passwords are hashed by Django."""
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=VIEWER)
    phone = models.CharField(max_length=15, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = ADMIN
        super().save(*args, **kwargs)

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return self.display_name
