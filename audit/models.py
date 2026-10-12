from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    ACTION_CHOICES = [('C', 'Created'), ('U', 'Updated'), ('D', 'Deleted')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='audit_entries')
    action = models.CharField(max_length=1, choices=ACTION_CHOICES)
    model = models.CharField(max_length=60, db_index=True)
    object_pk = models.CharField(max_length=40)
    object_repr = models.CharField(max_length=200)
    changes = models.JSONField(default=dict, blank=True)    # {field: [old, new]} for updates
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
