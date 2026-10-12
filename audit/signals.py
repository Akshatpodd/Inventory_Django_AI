"""Writes an audit entry whenever an important record is created, changed or deleted .

Stock movements are not listed here: the stock ledger itself is their audit trail.
"""
from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

from .middleware import get_current_user

AUDITED = ['accounts.User', 'catalog.Product', 'catalog.Category', 'catalog.ProductSupplier', 'suppliers.Supplier',
           'purchasing.PurchaseOrder', 'sales.Sale']
SKIP_FIELDS = {'password', 'last_login', 'failed_attempts', 'locked_until'}


def _log(**kwargs):
    from .models import AuditLog
    AuditLog.objects.create(user=get_current_user(), **kwargs)


def _before_save(sender, instance, **kwargs):
    instance._audit_changes = {}
    if instance.pk:
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old:
            for field in sender._meta.concrete_fields:
                if field.name in SKIP_FIELDS:
                    continue
                before, after = getattr(old, field.attname), getattr(instance, field.attname)
                if before == 'TMP':     # the automatic SKU / number assigned right after creation
                    continue
                if before != after:
                    instance._audit_changes[field.name] = [str(before), str(after)]


def _after_save(sender, instance, created, **kwargs):
    if created:
        _log(action='C', model=sender.__name__, object_pk=str(instance.pk), object_repr=str(instance)[:200])
    elif getattr(instance, '_audit_changes', None):
        _log(action='U', model=sender.__name__, object_pk=str(instance.pk), object_repr=str(instance)[:200],
             changes=instance._audit_changes)


def _after_delete(sender, instance, **kwargs):
    _log(action='D', model=sender.__name__, object_pk=str(instance.pk), object_repr=str(instance)[:200])


for label in AUDITED:
    model = apps.get_model(label)
    pre_save.connect(_before_save, sender=model, dispatch_uid=f'audit-pre-{label}')
    post_save.connect(_after_save, sender=model, dispatch_uid=f'audit-post-{label}')
    post_delete.connect(_after_delete, sender=model, dispatch_uid=f'audit-del-{label}')
